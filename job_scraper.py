#!/usr/bin/env python3
"""Daily job scan: fetch, filter, score, email.

Usage:
  python job_scraper.py             real run: sends the email, updates seen_jobs.json
  python job_scraper.py --dry-run   no email, no state change, writes preview.html
"""
import csv
import html
import io
import json
import os
import re
import smtplib
import ssl
import sys
import time
from dataclasses import dataclass, field
from functools import partial
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo

import requests

import config
import workday

ROOT = Path(__file__).parent
SEEN_FILE = ROOT / "seen_jobs.json"
APPLIED_FILE = ROOT / "applied.csv"
SPONSORS_FILE = ROOT / "sponsors.csv"
HEADERS = {"User-Agent": "personal-job-scraper/1.0 (personal use)"}
TIMEOUT = 25
NOW = datetime.now(timezone.utc)
FAILURES = []  # (kind, company, reason) for companies that could not be read
METRICS = {"adzuna_calls": 0, "adzuna_jobs": 0, "companies_ok": 0, "companies_total": 0}
COMPANIES_FILE = ROOT / "companies.csv"
ATS_SOURCES = ("greenhouse", "lever", "ashby", "workday")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class Job:
    source: str
    uid: str
    company: str
    title: str
    location: str
    url: str
    posted: datetime | None
    description: str
    track: str = ""
    score: float = 0.0
    resume: str = ""
    visa: str = ""  # "yes", "listed" or ""
    tags: list = field(default_factory=list)
    fit: int | None = None
    reason: str = ""
    flags: str = ""
    final: float = 0.0
    dropped: str = ""
    locations: list = field(default_factory=list)
    alt_uids: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def canonical_url(url):
    """Stable URL identity without tracking parameters, fragments or locale noise."""
    parts = urlsplit(url or "")
    host = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+(?:en-US|en-GB)/", "/", parts.path, flags=re.I).rstrip("/")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query)
                             if k.lower() not in {"utm_source", "utm_medium", "utm_campaign",
                                                   "utm_content", "utm_term", "ref", "source"}))
    return f"{host}{path.lower()}" + (f"?{query}" if query else "")


def job_identities(job):
    """Preserve ATS requisition IDs and canonical URLs; fallback for aggregators only."""
    keys = {job.uid}
    if job.url:
        keys.add("url:" + canonical_url(job.url))
    if job.source not in ATS_SOURCES:
        keys.add("role:" + ":".join((norm(job.company), norm(job.title), norm(job.location))))
    return keys


def parse_iso(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def get_json(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def name_match(names, text):
    """True if any name (aliases split by '|') appears as a whole word in text."""
    t = (text or "").lower()
    for entry in names:
        for alias in str(entry).split("|"):
            a = alias.strip().lower()
            if a and re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", t):
                return True
    return False


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def fetch_greenhouse(slug):
    data = get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        {"content": "true"},
    )
    for j in data.get("jobs", []):
        yield Job(
            source="greenhouse",
            uid=f"gh:{slug}:{j['id']}",
            company=config.COMPANY_NAMES.get(slug) or j.get("company_name") or slug.title(),
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", ""),
            url=j.get("absolute_url", ""),
            posted=parse_iso(j.get("first_published") or j.get("updated_at")),
            description=clean(j.get("content")),
        )


def fetch_lever(slug):
    data = get_json(f"https://api.lever.co/v0/postings/{slug}", {"mode": "json"})
    for j in data:
        created = j.get("createdAt")
        posted = (
            datetime.fromtimestamp(created / 1000, tz=timezone.utc) if created else None
        )
        loc = (j.get("categories") or {}).get("location") or ""
        if j.get("workplaceType") == "remote":
            loc += " Remote"
        yield Job(
            source="lever",
            uid=f"lv:{slug}:{j['id']}",
            company=config.COMPANY_NAMES.get(slug, slug.title()),
            title=j.get("text", ""),
            location=loc,
            url=j.get("hostedUrl", ""),
            posted=posted,
            description=j.get("descriptionPlain") or clean(j.get("description")),
        )


def fetch_ashby(slug):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        if j.get("isRemote"):
            loc += " Remote"
        yield Job(
            source="ashby",
            uid=f"ab:{slug}:{j['id']}",
            company=config.COMPANY_NAMES.get(slug, slug.title()),
            title=j.get("title", ""),
            location=loc,
            url=j.get("jobUrl", ""),
            posted=parse_iso(j.get("publishedAt")),
            description=j.get("descriptionPlain") or clean(j.get("descriptionHtml")),
        )


def _adzuna_search(params):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    base = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 50,
        "max_days_old": config.ADZUNA_MAX_DAYS,
        "sort_by": "date",
        "content-type": "application/json",
    }
    base.update(params)
    METRICS["adzuna_calls"] += 1
    data = get_json("https://api.adzuna.com/v1/api/jobs/us/search/1", base)
    for j in data.get("results", []):
        METRICS["adzuna_jobs"] += 1
        yield Job(
            source="adzuna",
            uid=f"az:{j['id']}",
            company=(j.get("company") or {}).get("display_name", ""),
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("display_name", ""),
            url=j.get("redirect_url", ""),
            posted=parse_iso(j.get("created")),
            description=clean(j.get("description")),
        )
    time.sleep(0.4)


ADZUNA_ERRORS = []


def fetch_adzuna():
    if not (os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")):
        print("adzuna: no keys set, skipping")
        return
    searches = []
    for query in config.ADZUNA_QUERIES:
        for where in config.ADZUNA_LOCATIONS:
            params = {"what": query}
            if where:
                params["where"] = where
            searches.append(params)
    for company in config.ADZUNA_COMPANIES:
        searches.append({"what_or": config.ADZUNA_COMPANY_WORDS, "company": company})

    failures = 0
    for params in searches:
        label = params.get("company") or params.get("what")
        try:
            yield from _adzuna_search(params)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            ADZUNA_ERRORS.append(f"adzuna: HTTP {code} on '{label}'")
            if code in (401, 403, 429):  # bad keys or over the limit: stop
                break
            failures += 1
        except Exception as e:
            ADZUNA_ERRORS.append(f"adzuna: {e} on '{label}'")
            failures += 1
        if failures >= 5:
            break


def load_companies():
    """Read companies.csv. Columns: name, ats, slug, tenant, board, subdomain, ..."""
    rows = []
    if COMPANIES_FILE.exists():
        with open(COMPANIES_FILE, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {k: (v or "").strip() for k, v in r.items() if k}
                if r.get("name") and r.get("ats"):
                    rows.append(r)
    return rows


def fetch_workday(row):
    def title_ok(t):
        return bool(track_for(t)) and not title_blocked(t)

    rows, note = workday.fetch(row, config.WORKDAY_TERMS, title_ok)
    print(f"workday/{row['name']}: {note}")
    for w in rows:
        yield Job(
            source="workday",
            uid=f"wd:{row['tenant']}:{w['req']}",
            company=row["name"],
            title=w["title"],
            location=w["location"],
            url=w["url"],
            posted=parse_iso(w["posted"]),
            description=w["description"],
        )


def build_plan():
    """List of (kind, label, function, display_name) to run."""
    rows = load_companies()
    plan = []
    if rows:
        for r in rows:
            ats, name = r["ats"].lower(), r["name"]
            if ats == "greenhouse" and r.get("slug"):
                plan.append((ats, name, partial(fetch_greenhouse, r["slug"]), name))
            elif ats == "lever" and r.get("slug"):
                plan.append((ats, name, partial(fetch_lever, r["slug"]), name))
            elif ats == "ashby" and r.get("slug"):
                plan.append((ats, name, partial(fetch_ashby, r["slug"]), name))
            elif ats == "workday" and r.get("tenant"):
                plan.append((ats, name, partial(fetch_workday, r), None))
        return plan
    # no companies.csv: fall back to the short lists in config.py
    plan += [("greenhouse", s, partial(fetch_greenhouse, s), None) for s in config.GREENHOUSE]
    plan += [("lever", s, partial(fetch_lever, s), None) for s in config.LEVER]
    plan += [("ashby", s, partial(fetch_ashby, s), None) for s in config.ASHBY]
    return plan


def fetch_all():
    jobs, errors, not_found = [], [], []
    plan = build_plan()
    METRICS["companies_total"] = len(plan)
    started, skipped = time.time(), 0
    for kind, label, fn, display in plan:
        if kind == "workday" and time.time() - started > config.FETCH_BUDGET_S:
            skipped += 1
            FAILURES.append((kind, label, "skipped: time limit reached"))
            continue
        try:
            got = list(fn())
            if display:
                for j in got:
                    j.company = display
            print(f"{kind}/{label}: {len(got)} jobs")
            jobs += got
            METRICS["companies_ok"] += 1
        except Exception as e:  # keep going if one company fails
            msg = str(e)
            print(f"{kind}/{label}: FAILED {msg}")
            FAILURES.append((kind, label, msg))
            if kind == "workday" and "could not find" in msg:
                not_found.append(label)
            else:
                errors.append(f"{kind}/{label}: {msg}")
        time.sleep(0.3)
    if not_found:
        print("workday names not found:", ", ".join(not_found))
        errors.append(
            f"workday: {len(not_found)} companies not found, tenant name probably wrong: "
            + ", ".join(not_found[:8]) + (" ..." if len(not_found) > 8 else "")
            + " (full list in the Actions log)"
        )
    if skipped:
        errors.append(f"workday: stopped early to save time, {skipped} companies skipped")
    try:
        got = list(fetch_adzuna())
        print(f"adzuna: {len(got)} jobs from {METRICS['adzuna_calls']} searches")
        jobs += got
        if ADZUNA_ERRORS:
            extra = f" (+{len(ADZUNA_ERRORS) - 1} more)" if len(ADZUNA_ERRORS) > 1 else ""
            errors.append(ADZUNA_ERRORS[0] + extra)
    except Exception as e:
        errors.append(f"adzuna: {e}")
        print(f"adzuna: FAILED {e}")
    return jobs, errors


# ---------------------------------------------------------------------------
# Titles, locations, visa signals
# ---------------------------------------------------------------------------
def track_for(title):
    t = title.lower()
    for key, track in config.TRACKS.items():
        if any(re.search(p, t) for p in track["patterns"]):
            return key
    return None


def title_blocked(title):
    t = title.lower()
    return any(re.search(p, t) for p in config.EXCLUDE_TITLE)


_STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC"
).split()
STATE_RE = re.compile(r"(?:,\s*|\(|\s-\s)(" + "|".join(_STATES) + r")\b")
STATE_NAMES_RE = re.compile(
    r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|"
    r"florida|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|"
    r"maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|"
    r"nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|"
    r"ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|"
    r"tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b",
    re.I,
)
US_RE = re.compile(r"\b(united states|usa|u\.s\.a?\.?|us|america)\b", re.I)
US_CITIES = [
    "phoenix", "philadelphia", "san antonio", "san diego", "jacksonville", "fort worth",
    "columbus", "charlotte", "indianapolis", "seattle", "denver", "washington, dc",
    "el paso", "nashville", "detroit", "oklahoma city", "portland", "las vegas",
    "memphis", "louisville", "baltimore", "milwaukee", "albuquerque", "tucson",
    "fresno", "sacramento", "kansas city", "mesa", "omaha", "colorado springs",
    "raleigh", "miami", "long beach", "virginia beach", "minneapolis", "tulsa",
    "tampa", "arlington", "new orleans", "wichita", "cleveland", "bakersfield",
    "santa clara", "bellevue", "cambridge, ma", "pittsburgh", "cincinnati",
    "st. louis", "saint louis", "salt lake city", "orlando", "charleston", "richmond",
    "hartford", "stamford", "greenwich", "parsippany", "bentonville", "plano", "irving",
    "frisco", "round rock", "scottsdale", "tempe", "boulder", "ann arbor", "madison",
    "des moines", "lexington", "providence", "buffalo", "rochester", "newark",
    "jersey city", "white plains", "princeton", "cary", "durham", "boise", "honolulu",
    "anchorage", "san mateo", "south san francisco", "irvine", "burbank", "pasadena",
    "el segundo", "culver city", "fort lauderdale", "west palm beach", "jacksonville",
    "chandler", "lehi", "draper", "alpharetta", "norwalk", "purchase, ny",
]
NON_US_RE = re.compile(
    r"\b(london|uk|united kingdom|england|scotland|wales|ireland|dublin|germany|"
    r"berlin|munich|hamburg|frankfurt|france|paris|netherlands|amsterdam|spain|"
    r"madrid|barcelona|italy|milan|rome|sweden|stockholm|poland|warsaw|krakow|"
    r"switzerland|zurich|geneva|denmark|copenhagen|norway|oslo|finland|helsinki|"
    r"portugal|lisbon|belgium|brussels|austria|vienna|czech|prague|hungary|"
    r"budapest|romania|bucharest|greece|athens|cyprus|bulgaria|serbia|croatia|"
    r"slovakia|slovenia|lithuania|latvia|estonia|iceland|luxembourg|malta|ukraine|"
    r"russia|belarus|"
    r"india|bangalore|bengaluru|mumbai|delhi|new delhi|gurgaon|gurugram|noida|"
    r"hyderabad|pune|chennai|kolkata|ahmedabad|sri lanka|nepal|bangladesh|dhaka|"
    r"singapore|japan|tokyo|osaka|korea|seoul|china|shanghai|beijing|shenzhen|"
    r"guangzhou|hong kong|taiwan|taipei|myanmar|cambodia|mongolia|kazakhstan|"
    r"australia|sydney|melbourne|brisbane|new zealand|auckland|"
    r"canada|toronto|vancouver|montreal|ottawa|calgary|"
    r"mexico|mexico city|brazil|sao paulo|argentina|buenos aires|colombia|bogota|"
    r"chile|santiago|peru|lima|costa rica|panama|ecuador|uruguay|venezuela|"
    r"uae|dubai|abu dhabi|saudi|ksa|riyadh|jeddah|qatar|doha|kuwait|bahrain|oman|"
    r"jordan|amman|lebanon|beirut|iraq|egypt|cairo|israel|tel aviv|morocco|tunisia|"
    r"pakistan|lahore|karachi|islamabad|"
    r"emea|apac|latam|mena|gcc|europe|asia|middle east|"
    r"nigeria|lagos|kenya|nairobi|south africa|cape town|ghana|ethiopia|uganda|"
    r"tanzania|rwanda|"
    r"philippines|manila|indonesia|jakarta|vietnam|thailand|bangkok|malaysia|"
    r"kuala lumpur|turkey|istanbul)\b",
    re.I,
)


def location_info(loc, desc=""):
    """Return (kind, points). kind: tier1, us, remote, unknown or non_us.

    US only is a whitelist: a place has to look American to pass.
    """
    loc = loc or ""
    l = loc.lower()
    if any(c in l for c in config.TIER1_CITIES) or re.search(r",\s*(TX|MA)\b", loc):
        return "tier1", config.LOC_POINTS_TIER1
    if re.fullmatch(r"\s*(remote|work from home|wfh)\s*", l):
        return "remote", config.LOC_POINTS_REMOTE
    if (US_RE.search(loc) or STATE_RE.search(loc) or STATE_NAMES_RE.search(loc)
            or any(c in l for c in US_CITIES)):
        return "us", (config.LOC_POINTS_REMOTE if "remote" in l else config.LOC_POINTS_OTHER_US)
    if NON_US_RE.search(l):
        return "non_us", 0
    if ("remote" in l or re.match(r"^\s*\d+\s+locations?\s*$", l)) and re.search(
            r"\b(united states|u\.s\.|us-based|within the us|across the us)\b", (desc or "").lower()):
        return "us", config.LOC_POINTS_REMOTE
    return "unknown", 0


NO_SPONSOR = [
    r"(will|does|do|can|could|is|are|would) not (be able to )?(provide |offer |support )?(visa |employment )?sponsor",
    r"(unable|not able) to (provide |offer )?(visa |employment )?sponsor",
    r"cannot (provide |offer )?(visa |employment )?sponsor",
    r"can.t (provide |offer )?(visa |employment )?sponsor",
    r"\bno (visa |employment )?sponsorship",
    r"without (the need for )?(current or future )?(visa |employer |employment )?sponsorship",
    r"not (require|need|requiring) (visa |employer |employment )?sponsorship",
    r"sponsorship (is |are )?not (available|offered|provided)",
    r"not (eligible|available) for (visa |employment )?sponsorship",
]
YES_SPONSOR = [
    r"(visa |employment )?sponsorship (is |are )?(available|provided|offered)",
    r"we (will |do |can )?(offer |provide )?(visa |employment )?sponsor",
    r"(?<![a-z])(?<!not )(will|can|able to) (provide )?(visa )?sponsor",
    r"h-?1b (sponsorship|transfer)",
    r"(open|willing) to (visa )?sponsor",
]


def sponsor_signal(text):
    """Return 'no', 'yes' or '' based on what the posting says."""
    t = (text or "").lower()
    neg = any(re.search(p, t) for p in NO_SPONSOR)
    pos = any(re.search(p, t) for p in YES_SPONSOR)
    if neg and not pos:
        return "no"
    if pos and not neg:
        return "yes"
    return ""


def load_sponsors():
    names = []
    if SPONSORS_FILE.exists():
        with open(SPONSORS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("company"):
                    names.append(row["company"].strip())
    return names


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def level_points(title):
    t = title.lower()
    if re.search(r"\b(senior|sr\.?|lead|manager)\b", t):
        return 10
    if re.search(r"\b(associate|specialist)\b", t):
        return 3
    return 0


def pick_resume(job):
    d = job.description.lower()
    ai_hits = len(re.findall(
        r"\b(artificial intelligence|machine learning|llm|llms|generative ai|genai|foundation models?)\b", d))
    if name_match(config.AI_COMPANIES, job.company) or ai_hits >= 4:
        return "AI/Tech resume"
    return "Commercial resume"


def applied_info(company, companies):
    """Return (found, latest_date_or_None) for a company in applied.csv."""
    found, latest = False, None
    for name, d in companies.items():
        if name_match([name], company):
            found = True
            if d and (latest is None or d > latest):
                latest = d
    return found, latest


def rule_score(job, companies, sponsors):
    t = job.title.lower()
    d = job.description.lower()
    flags = []

    s = config.TRACKS[job.track]["weight"]
    s += level_points(job.title)
    s += location_info(job.location, job.description)[1]

    if job.posted:
        hrs = (NOW - job.posted).total_seconds() / 3600
        if hrs <= 24:
            s += config.FRESH_24H_BONUS
        elif hrs <= 72:
            s += config.FRESH_72H_BONUS

    if job.source in ATS_SOURCES:
        s += config.ATS_BONUS
    if name_match(config.TARGET_COMPANIES, job.company):
        s += config.TARGET_COMPANY_BONUS
        job.tags.append("Target")

    found, latest = applied_info(job.company, companies)
    if not found:
        s += config.NEW_COMPANY_BONUS
        job.tags.append("New")
    elif latest is None:
        s -= 6
        flags.append("applied here before")
    else:
        age = (NOW.date() - latest).days
        if age <= config.COMPANY_COOLDOWN_DAYS:
            s -= 12
            flags.append(f"applied here {age}d ago")

    hits = sum(1 for k in config.POSITIVE_KEYWORDS if re.search(r"\b" + re.escape(k), d))
    s += min(24, 2 * hits)
    bad = [k for k in config.NEGATIVE_KEYWORDS if re.search(r"\b" + re.escape(k), d)]
    s -= min(24, 8 * len(bad))
    if bad:
        flags.append("mentions: " + ", ".join(bad[:3]))

    yrs = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", d)]
    yrs = [y for y in yrs if y <= 20]
    if yrs:
        top = max(yrs)
        if top >= 12:
            s -= 10
            flags.append(f"asks {top}+ yrs")
        elif top <= 2:
            s -= 8
            flags.append("very junior ask")

    sig = sponsor_signal(job.description)
    if sig == "yes":
        job.visa = "yes"
        s += config.SAYS_SPONSORS_BONUS
    elif sig == "no":
        job.visa = "no"
        s -= config.NO_SPONSOR_PENALTY
    elif name_match(sponsors, job.company):
        job.visa = "listed"
        s += config.ON_SPONSOR_LIST_BONUS

    job.score = s
    job.flags = "; ".join(flags)
    job.resume = pick_resume(job)


def domain_check(job):
    """Return a reason if the description is off-topic, else None."""
    d = job.description.lower()
    if len(d) < 300:  # too short to judge (for example, details not fetched)
        return None
    off = sum(1 for w in config.OFF_DOMAIN_WORDS if re.search(r"\b" + re.escape(w), d))
    if off >= config.OFF_DOMAIN_HITS:
        return "off-topic (advertising, cloud or similar)"
    on = sum(1 for w in config.DOMAIN_WORDS if re.search(r"\b" + re.escape(w), d))
    if on < config.MIN_DOMAIN_HITS:
        return "description does not match your background"
    return None


def merge_same_roles(jobs):
    """One row per company and title. All cities are listed on that row."""
    groups, order = {}, []
    for j in jobs:  # already sorted best first
        k = (norm(j.company), norm(j.title))
        if k not in groups:
            j.locations = [j.location] if j.location else []
            j.alt_uids = []
            groups[k] = j
            order.append(k)
        else:
            rep = groups[k]
            if j.location and j.location not in rep.locations:
                rep.locations.append(j.location)
            rep.alt_uids.append(j.uid)
    return [groups[k] for k in order]


def shortlist(jobs, seen, applied, sponsors=None):
    exact, companies = applied
    sponsors = sponsors or []
    cutoff = NOW - timedelta(hours=config.MAX_AGE_HOURS)
    stats = dict(fetched=len(jobs), stale=0, title=0, seen=0, applied=0,
                 non_us=0, domain=0, no_sponsor=0, dupe=0, low=0, merged=0)
    out, keys = [], set()

    def drop(j, key, label):
        stats[key] += 1
        j.dropped = label

    for j in jobs:
        if not j.url or not j.title:
            continue
        if j.posted and j.posted < cutoff:
            drop(j, "stale", "too old")
            continue
        track = track_for(j.title)
        if not track or title_blocked(j.title):
            drop(j, "title", "title or level not a match")
            continue
        if any(k in seen for k in job_identities(j)):
            drop(j, "seen", "already emailed before")
            continue
        if (norm(j.company), norm(j.title)) in exact or j.url in exact:
            drop(j, "applied", "already applied")
            continue
        if config.US_ONLY and location_info(j.location, j.description)[0] in ("non_us", "unknown"):
            drop(j, "non_us", "outside the US or location not clearly US")
            continue
        why = domain_check(j)
        if why:
            drop(j, "domain", why)
            continue
        if config.DROP_NO_SPONSORSHIP and sponsor_signal(j.description) == "no":
            drop(j, "no_sponsor", "says no sponsorship")
            continue
        key = canonical_url(j.url) if j.url else (norm(j.company), norm(j.title), norm(j.location))
        if key in keys:
            drop(j, "dupe", "duplicate")
            continue
        keys.add(key)
        j.track = track
        rule_score(j, companies, sponsors)
        if j.score < config.MIN_SCORE:
            drop(j, "low", f"score {round(j.score)} below {config.MIN_SCORE}")
            continue
        out.append(j)
    out.sort(key=lambda x: x.score, reverse=True)
    before = len(out)
    out = merge_same_roles(out)
    stats["merged"] = before - len(out)
    return out, stats


# ---------------------------------------------------------------------------
# Optional LLM review
# ---------------------------------------------------------------------------
def llm_review(job):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return
    prompt = (
        "You are a blunt recruiter judging job fit. Be strict. Most jobs "
        "should score between 4 and 7. Only give 9 or 10 for a near-perfect match. "
        "Judge skills, level and industry fit only.\n\n"
        f"CANDIDATE:\n{config.PROFILE_SUMMARY}\n\n"
        f"JOB:\nCompany: {job.company}\nTitle: {job.title}\n"
        f"Location: {job.location}\nDescription:\n{job.description[:6000]}\n\n"
        'Reply with JSON only, no other text: {"fit": <integer 1-10>, '
        '"reason": "<max 25 words, plain language>", '
        '"dealbreakers": "<short, or empty string>"}'
    )
    for attempt in range(2):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": config.LLM_MODEL,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            if r.status_code == 429:
                time.sleep(5)
                continue
            r.raise_for_status()
            text = r.json()["content"][0]["text"]
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0))
            job.fit = max(1, min(10, int(data["fit"])))
            job.reason = str(data.get("reason", "")).strip()
            dealbreak = str(data.get("dealbreakers", "")).strip()
            if dealbreak:
                job.flags = (job.flags + "; " if job.flags else "") + dealbreak
            return
        except Exception as e:
            print(f"llm review failed for {job.title}: {e}")
            return


def base_title(title):
    return norm(re.split(r"[,\-\u2013|(:/]", title)[0])


def cap_per_company(jobs):
    """At most MAX_PER_COMPANY different roles per company.

    Roles with the same main title (for example "Account Executive, Retail" and
    "Account Executive, Travel") count as one, and the same role in several
    cities counts once.
    """
    families, out = {}, []
    for j in jobs:
        fam = families.setdefault(norm(j.company), [])
        b = base_title(j.title)
        if b in fam or len(fam) < config.MAX_PER_COMPANY:
            if b not in fam:
                fam.append(b)
            out.append(j)
    return out


def rank(pool):
    """Review the top of the pool with the LLM (if a key is set) and rank.

    Returns (top, rejected). Only emailed and rejected jobs are marked as seen,
    so anything that missed the cut can show up again tomorrow.
    """
    pool = cap_per_company(pool)[: config.LLM_POOL]
    if not os.getenv("ANTHROPIC_API_KEY"):
        for j in pool:
            j.final = j.score
        return pool[: config.TOP_N], []
    for j in pool:
        llm_review(j)
        time.sleep(0.3)
    rejected = [j for j in pool if j.fit is not None and j.fit < config.MIN_FIT]
    kept = [j for j in pool if j.fit is None or j.fit >= config.MIN_FIT]
    for j in rejected:
        j.dropped = f"AI fit {j.fit}/10"
    for j in kept:
        j.final = j.score + (j.fit or 5) * 8
    kept.sort(key=lambda x: x.final, reverse=True)
    return cap_per_company(kept)[: config.TOP_N], rejected


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
TRACK_LABEL = {k: v["label"] for k, v in config.TRACKS.items()}
VISA_LABEL = {"yes": "Says it sponsors", "listed": "On sponsor list",
              "no": "Says no sponsorship", "": "Unknown"}


def where_text(j):
    locs = j.locations or ([j.location] if j.location else [])
    text = "; ".join(locs[:3])[:90]
    extra = len(locs) - 3
    return text + (f" (+{extra} more)" if extra > 0 else "")


def age_text(j):
    if not j.posted:
        return "new"
    h = (NOW - j.posted).total_seconds() / 3600
    return f"{int(max(h, 0))}h" if h < 48 else f"{int(h // 24)}d"


def build_email(top, stats, errors):
    esc = html.escape
    rows = []
    for i, j in enumerate(top, 1):
        fit = f"{j.fit}/10" if j.fit else "n/a"
        note = esc(j.reason)
        if j.flags:
            note += f'<br><span style="color:#b45309">{esc(j.flags)}</span>'
        badges = "".join(
            f' <span style="background:#e0f2fe;border-radius:3px;padding:0 4px;'
            f'font-size:11px">{esc(t)}</span>'
            for t in j.tags
        )
        rows.append(
            "<tr>"
            f"<td>{i}</td><td>{fit}</td>"
            f'<td><a href="{esc(j.url)}">{esc(j.title)}</a><br>'
            f'<span style="color:#555">{esc(j.company)}</span>{badges}</td>'
            f"<td>{esc(where_text(j))}</td>"
            f"<td>{esc(TRACK_LABEL.get(j.track, j.track))}</td>"
            f"<td>{esc(j.resume)}</td><td>{esc(VISA_LABEL.get(j.visa, ''))}</td>"
            f"<td>{age_text(j)}</td><td>{note}</td>"
            "</tr>"
        )
    table = (
        '<table cellpadding="6" cellspacing="0" border="1" '
        'style="border-collapse:collapse;border-color:#ddd;font-size:13px">'
        "<tr style='background:#f3f4f6'><th>#</th><th>Fit</th><th>Role</th>"
        "<th>Where</th><th>Track</th><th>Resume</th><th>Visa</th><th>Age</th>"
        "<th>Notes</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    no_sp = (f"{stats['no_sponsor']} saying no sponsorship, "
             if config.DROP_NO_SPONSORSHIP else "")
    footer = (
        f"<p style='color:#666;font-size:12px'>Scanned {stats['fetched']} jobs. "
        f"Dropped: {stats['stale']} old, {stats['title']} wrong title or level, "
        f"{stats['non_us']} outside the US or unclear location, "
        f"{stats['domain']} off-topic by description, {no_sp}"
        f"{stats['seen']} already sent, {stats['applied']} already applied, "
        f"{stats['dupe']} duplicates, {stats['low']} low score. "
        f"{stats['merged']} repeat postings merged into one row. "
        f"Adzuna: {METRICS['adzuna_calls']} searches, {METRICS['adzuna_jobs']} jobs. "
        f"Companies read directly: {METRICS['companies_ok']} of {METRICS['companies_total']}.</p>"
        "<p style='color:#666;font-size:12px'>Visa column: most postings say nothing, "
        "so Unknown is normal. \"Says no sponsorship\" rows are kept but ranked lower. "
        "\"On sponsor list\" only means the company has filed "
        "H-1B petitions before, not that it will sponsor this role. Always check.</p>"
    )
    if errors:
        footer += (
            "<p style='color:#b91c1c;font-size:12px'>Sources that failed "
            "(fix the row in companies.csv or delete it; the attached companies_to_fix.csv has the full list):<br>"
            + "<br>".join(esc(e) for e in errors[:40])
            + (f"<br>(+{len(errors) - 40} more)" if len(errors) > 40 else "")
            + "</p>"
        )
    body = (
        '<div style="font-family:Arial,sans-serif">'
        + (table if top else "<p>No new matches today.</p>")
        + footer
        + "</div>"
    )
    text = "\n".join(
        f"{i}. [{j.fit or '-'}] {j.title} | {j.company} | {j.location} | {j.resume} | {j.url}"
        for i, j in enumerate(top, 1)
    ) or "No new matches today."
    return body, text


def build_csv(jobs):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["final", "fit", "track", "resume", "visa", "tags", "company",
                "title", "location", "posted", "url", "reason", "flags"])
    for j in jobs:
        w.writerow([
            round(j.final, 1), j.fit or "", TRACK_LABEL.get(j.track, j.track),
            j.resume, VISA_LABEL.get(j.visa, ""), " ".join(j.tags), j.company,
            j.title, "; ".join(j.locations) or j.location, j.posted.isoformat() if j.posted else "",
            j.url, j.reason, j.flags,
        ])
    return buf.getvalue().encode("utf-8")


def build_failures_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "company", "reason"])
    for kind, label, reason in FAILURES:
        w.writerow([kind, label, reason[:200]])
    return buf.getvalue().encode("utf-8")


def send_email(subject, body, text, csv_bytes):
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to = os.getenv("MAIL_TO") or user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(body, subtype="html")
    msg.add_attachment(csv_bytes, maintype="text", subtype="csv", filename="jobs.csv")
    if FAILURES:
        msg.add_attachment(build_failures_csv(), maintype="text", subtype="csv",
                           filename="companies_to_fix.csv")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, password)
        s.send_message(msg)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def load_seen():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=0, sort_keys=True))


def load_applied():
    """applied.csv columns: company,title,url,date (only company is required).

    A row with just a company means "I have applied there". Add a date
    (YYYY-MM-DD) to get a warning for recent applications.
    Returns (exact, companies): exact job matches and a company -> date map.
    """
    exact, companies = set(), {}
    if APPLIED_FILE.exists():
        with open(APPLIED_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                company = (row.get("company") or "").strip()
                title = (row.get("title") or "").strip()
                url = (row.get("url") or "").strip()
                if url:
                    exact.add(url)
                if company and title:
                    exact.add((norm(company), norm(title)))
                if company:
                    d = None
                    try:
                        d = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
                    except ValueError:
                        pass
                    prev = companies.get(company)
                    companies[company] = max(d, prev) if (d and prev) else (d or prev)
    return exact, companies


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(jobs, errors, seen, applied, sponsors=None):
    pool, stats = shortlist(jobs, seen, applied, sponsors)
    top, rejected = rank(pool)
    return top, rejected, stats


def print_debug(jobs, top):
    """Show what happened to jobs from DEBUG_COMPANIES in the run log."""
    names = config.DEBUG_COMPANIES
    if not names:
        return
    emailed = {id(j) for j in top}
    merged_uids = {u for j in top for u in j.alt_uids}
    print("--- debug: jobs from DEBUG_COMPANIES ---")
    found = False
    for j in jobs:
        if name_match(names, j.company):
            found = True
            status = "EMAILED" if id(j) in emailed else (
                "EMAILED (merged into another city's row)" if j.uid in merged_uids else (
                    j.dropped or "passed filters, not in top list"))
            print(f"{j.company} | {j.title} | {j.location} | {age_text(j)} | {status}")
    if not found:
        print("none fetched (check the slug in config.py)")


def main():
    dry = "--dry-run" in sys.argv
    seen, applied, sponsors = load_seen(), load_applied(), load_sponsors()
    jobs, errors = fetch_all()
    top, rejected, stats = run(jobs, errors, seen, applied, sponsors)
    print_debug(jobs, top)
    body, text = build_email(top, stats, errors)
    local = NOW.astimezone(ZoneInfo("America/Chicago"))
    subject = f"{len(top)} new roles for you, {local:%a %b %d}"

    if dry:
        (ROOT / "preview.html").write_text(body, encoding="utf-8")
        print(f"Dry run: {len(top)} roles. Wrote preview.html")
        return

    send_email(subject, body, text, build_csv(top))
    for j in top + rejected:
        for uid in job_identities(j) | set(j.alt_uids):
            seen[uid] = NOW.isoformat()
    save_seen(seen)
    print(f"Sent {len(top)} roles.")


if __name__ == "__main__":
    main()
