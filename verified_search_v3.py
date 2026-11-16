"""Verified job discovery v3. Read-only: never applies or sends mail.

Inspired by the daily-job-search methodology by Heidi Miller (MIT License).
The upstream community feed is candidate discovery ONLY; every emailed role must
be confirmed against its own employer's ATS and pass publication-age checks.
"""
import argparse
import concurrent.futures
import csv
import gzip
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests

MANIFEST_URL = "https://raw.githubusercontent.com/Riley-Dorrington/job-board-data/main/data/chunks/jobs_manifest.json"
PROFILE = {
    "age_hours": 72,
    "max_posted_days": 21,
    "max_verify": 110,
    "max_results": 15,
    "max_per_company": 1,
    "cooldown_until": "2027-02-13",
    "cooldown_companies": ["datadog", "okta", "via", "stripe", "doordash", "ramp", "databricks"],
}
TITLE_INCLUDE = [
    r"\bpartnerships?\b", r"\bpartner(?:ship)? (?:development|manager|success|sales|channels?)\b",
    r"\bbusiness development\b", r"\b(?:commercial|sales|channel|category|vendor|supplier|marketplace) (?:manager|lead|strategy)\b",
    r"\b(?:enterprise|strategic|key|national|global) account (?:manager|management|lead)\b",
    r"\baccount manager\b", r"\bcustomer (?:development|success) manager\b",
    r"\brevenue growth\b", r"\bgo.to.market\b", r"\balliances? manager\b",
]
TITLE_EXCLUDE = [
    r"\b(?:intern|internship|graduate trainee|entry.level|junior|sdr|bdr)\b",
    r"\b(?:engineer|engineering|architect|developer|scientist|administrator|recruiter|counsel|attorney)\b",
    r"\b(?:solution(?:s)?|technical|devops|cybersecurity|infrastructure|cloud|implementation)\b",
    r"\b(?:product|program|project) manager\b", r"\b(?:retail|field|inside) sales (?:representative|associate)\b",
    r"\b(?:accountant|accounting|auditor|controller|analyst|designer|territory sales)\b",
    r"\b(?:vice president|chief|president|head of|intern)\b",
]
HARD_TECHNICAL = [
    r"(?:required?|must have|hands.on|experience with|proficiency in)[^.]{0,95}(?:software engineering|cloud architecture|aws architecture|azure architecture|gcp architecture|ci/cd|devsecops|kubernetes|solution architecture|llm framework|agent framework|mcp server)",
    r"\b(?:architecting|building) (?:cloud|production) (?:systems|infrastructure|integrations)\b",
    r"\b(?:coding|programming) (?:in |with )?(?:python|java|go|typescript)\b",
]
EXCLUDE_EMPLOYERS = {"jobgether", "theladders", "ladders"}
US_HINTS = ("united states", "usa", "u.s.", "us-remote", "remote us", "us remote",
            "chicago", "new york", "brooklyn", "manhattan", "san francisco",
            "bay area", "los angeles", "atlanta", "houston", "dallas", "austin",
            "boston", "seattle", "denver", "miami", "phoenix", "philadelphia",
            "california", "illinois", "texas", "washington, dc")
STATE_ABBR = re.compile(r"(?:,\s*|\bUS[-\s]+)(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b", re.I)
FOREIGN = ("canada", "toronto", "vancouver", "united kingdom", "london", "india",
           "singapore", "germany", "berlin", "france", "paris", "poland",
           "australia", "netherlands", "spain", "mexico", "brazil")
PREFERRED = ("chicago", "new york", "san francisco", "los angeles", "bay area",
             "houston", "dallas", "atlanta", "boston", "austin")
CLOSED_WORDS = ("job is no longer available", "no longer accepting applications",
                "this position has been closed", "job posting has expired")
DATE_TEXT = re.compile(r"\b(\d+)\s*\+?\s*(hours?|days?|weeks?|months?)\s+ago\b", re.I)


def clean(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))).strip()


def age_days(value, now=None):
    """Only employer-source publication time; never first_seen or updated_at."""
    now = now or datetime.now(timezone.utc)
    if value is None or value == "":
        return None
    if isinstance(value, (float, int)):
        try:
            d = datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    else:
        s = str(value).strip()
        lower = s.lower()
        if lower in ("today", "posted today", "just posted"):
            return 0.0
        if lower in ("yesterday", "posted yesterday"):
            return 1.0
        match = DATE_TEXT.search(s)
        if match:
            count = int(match.group(1))
            unit = match.group(2).lower()
            return count * (1/24 if unit.startswith("hour") else 7 if unit.startswith("week") else 30 if unit.startswith("month") else 1)
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
    age = (now - d).total_seconds() / 86400
    return max(0, age) if age >= -1 else None


def canon(value):
    return re.sub(r"\W+", "", str(value or "").lower())


def title_key(value):
    text = str(value or "").lower()
    text = re.sub(r"\b(sr|senior|ii|iii|iv|lead)\b", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def location_ok(job):
    loc = str(job.get("location") or "").lower()
    if any(s in loc for s in FOREIGN) and not any(s in loc for s in US_HINTS):
        return False
    # The community feed's remote=True is not US employment eligibility.
    return any(s in loc for s in US_HINTS) or bool(STATE_ABBR.search(loc))


def commercial_title(title):
    title = str(title or "").lower()
    return bool(any(re.search(p, title) for p in TITLE_INCLUDE)) and not any(
        re.search(p, title) for p in TITLE_EXCLUDE)


def load_applied(path):
    if not Path(path).exists():
        return [], "tracker_missing"
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    return rows, "ok"


def tracker_match(job, applied):
    company = canon(job["company"])
    title = title_key(job["title"])
    joburl = job["url"].rstrip("/").lower()
    known_company = False
    for row in applied:
        if canon(row.get("company")) != company:
            continue
        known_company = True
        if row.get("url") and row["url"].rstrip("/").lower() == joburl:
            return "already_applied"
        oldtitle = title_key(row.get("title"))
        if oldtitle and (oldtitle == title or (len(oldtitle) > 15 and (oldtitle in title or title in oldtitle))):
            return "already_applied"
    return "prior_company" if known_company else "new_company"


def first_seen_recent(job, now, hours):
    raw = job.get("first_seen")
    if not raw:
        return False
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age = (now - when).total_seconds() / 3600
    return -1 <= age <= hours


def candidate_gate(job, applied, now, hours):
    if not all(job.get(k) for k in ("company", "title", "url")):
        return "missing_fields"
    if job.get("is_recruiter") or canon(job["company"]) in EXCLUDE_EMPLOYERS:
        return "recruiter"
    if not commercial_title(job["title"]):
        return "title_not_commercial"
    if not location_ok(job):
        return "location_unverified"
    if not first_seen_recent(job, now, hours):
        return "not_recent_to_feed"
    if job["url"].startswith("http://") or not job["url"].startswith("https://"):
        return "unsafe_url"
    if canon(job["company"]) in {canon(v) for v in PROFILE["cooldown_companies"]} and now.date().isoformat() <= PROFILE["cooldown_until"]:
        return "repeat_employer_cooldown"
    match = tracker_match(job, applied)
    if match == "already_applied":
        return match
    return "candidate"


def candidate_score(job, prior):
    title = job["title"].lower()
    loc = str(job.get("location") or "").lower()
    base = 45
    if "partnership" in title or "business development" in title:
        base += 15
    if "category" in title or "vendor" in title or "supplier" in title:
        base += 14
    if "strategic account" in title or "enterprise account" in title:
        base += 12
    if "manager" in title:
        base += 8
    if "senior" in title or "sr " in title:
        base += 3
    if any(city in loc for city in PREFERRED):
        base += 7
    if prior == "new_company":
        base += 10
    return base


def fetch_manifest(manifest, session):
    response = session.get(manifest, timeout=25)
    response.raise_for_status()
    data = response.json()
    chunks = data.get("chunks", [])
    if not isinstance(chunks, list) or not chunks or len(chunks) > 120:
        raise ValueError("Invalid/oversized source feed manifest")
    if not all(re.fullmatch(r"jobs_chunk_\d+\.json\.gz", c) for c in chunks):
        raise ValueError("Unexpected feed chunk filenames")
    if not manifest.startswith("https://"):
        raise ValueError("Manifest must use HTTPS")
    return data


def fetch_chunk(url):
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    if len(response.content) > 16_000_000:
        raise ValueError("Oversized feed chunk")
    return json.loads(gzip.decompress(response.content))


def discover(manifest, applied, session=None, now=None, hours=None, max_verify=None):
    session = session or requests.Session()
    now = now or datetime.now(timezone.utc)
    hours = hours or PROFILE["age_hours"]
    max_verify = max_verify or PROFILE["max_verify"]
    data = fetch_manifest(manifest, session)
    base = manifest.rsplit("/", 1)[0]
    counts, candidates, seen = Counter(), [], set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for n, block in enumerate(pool.map(fetch_chunk, (base + "/" + c for c in data["chunks"]))):
            if not isinstance(block, list):
                raise ValueError("Chunk is not a list")
            counts["feed_jobs"] += len(block)
            for j in block:
                reason = candidate_gate(j, applied, now, hours)
                counts[reason] += 1
                if reason != "candidate":
                    continue
                url = j["url"].split("?")[0].rstrip("/")
                if url in seen:
                    counts["duplicate_url"] += 1
                    continue
                seen.add(url)
                job = {k:j.get(k) for k in ("company", "title", "location", "url", "ats", "first_seen",
                                          "remote", "workplaceType", "salary")}
                job["prior"] = tracker_match(job, applied)
                job["score"] = candidate_score(job, job["prior"])
                candidates.append(job)
            if (n + 1) % 10 == 0:
                print("Read chunks:", n + 1, "of", len(data["chunks"]), "candidates:", len(candidates), flush=True)
    candidates.sort(key=lambda j: (-j["score"], j["company"].lower(), j["title"].lower()))
    # Never allow the largest hiring company to consume the entire verification budget.
    per_company = Counter()
    selected = []
    for job in candidates:
        company = canon(job["company"])
        if per_company[company] >= 2:
            continue
        selected.append(job)
        per_company[company] += 1
        if len(selected) >= max_verify:
            break
    counts["verification_queue"] = len(selected)
    counts["feed_candidates"] = len(candidates)
    return selected, counts, data


def verified_url(job):
    u = urlparse(job["url"])
    host = (u.hostname or "").lower()
    segments = [unquote(p) for p in u.path.strip("/").split("/") if p]
    if not host or any(p in (".", "..") for p in segments):
        return None
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and len(segments) >= 3 and segments[-2] == "jobs":
        return "greenhouse", "https://boards-api.greenhouse.io/v1/boards/{}/jobs/{}".format(segments[0], segments[-1])
    if host == "jobs.lever.co" and len(segments) >= 2:
        return "lever", "https://api.lever.co/v0/postings/{}/{}".format(segments[0], segments[1])
    if host == "jobs.ashbyhq.com" and len(segments) >= 2:
        return "ashby", "https://api.ashbyhq.com/posting-api/job-board/{}".format(segments[0])
    if host.endswith(".myworkdayjobs.com") and re.fullmatch(r"[^.]+\.wd\d+\.myworkdayjobs\.com", host):
        tenant = host.split(".")[0]
        if "job" in segments:
            ix = segments.index("job")
            site = segments[ix-1] if ix >= 1 else ""
            if site and ix + 1 < len(segments):
                suffix = "/".join(segments[ix+1:])
                return "workday", "https://{}/wday/cxs/{}/{}/job/{}".format(host, tenant, site, suffix)
    # Everything else goes to manual verification; never claim it is open.
    return None


def verify(job, now=None, session=None):
    now = now or datetime.now(timezone.utc)
    session = session or requests.Session()
    target = verified_url(job)
    if not target:
        return None, "unsupported_ats"
    ats, endpoint = target
    try:
        response = session.get(endpoint, timeout=14, headers={"Accept":"application/json"})
        if response.status_code in (404, 410):
            return None, "closed"
        response.raise_for_status()
        result = response.json()
        if ats == "greenhouse":
            title = result.get("title") or ""
            content = clean(result.get("content") or "")
            published = result.get("first_published") or result.get("created_at")
            verified_location = (result.get("location") or {}).get("name", "")
            open_status = True
        elif ats == "lever":
            title = result.get("text") or ""
            content = clean(" ".join([str(result.get("descriptionPlain") or ""), str(result.get("additionalPlain") or ""), " ".join(str(section.get("content") or "") for section in result.get("lists", []) if isinstance(section, dict))]))
            published = result.get("createdAt")
            verified_location = (result.get("categories") or {}).get("location") or ""
            open_status = True
        elif ats == "ashby":
            path_parts = urlparse(job["url"]).path.strip("/").split("/")
            jobid = path_parts[1]
            found = next((item for item in result.get("jobs", []) if str(item.get("id")) == jobid), None)
            if not found:
                return None, "closed"
            title = found.get("title") or ""
            content = clean(found.get("descriptionPlain") or found.get("descriptionHtml") or "")
            published = found.get("publishedAt")
            verified_location = found.get("location") or ""
            open_status = found.get("isListed", True) is not False
        else:
            info = result.get("jobPostingInfo") or {}
            title = info.get("title") or result.get("title") or ""
            content = clean(info.get("jobDescription") or result.get("jobDescription") or "")
            published = info.get("postedOn") or result.get("postedOn")
            verified_location = info.get("location") or job.get("location") or ""
            open_status = result.get("canApply", info.get("canApply")) is not False
        if not open_status:
            return None, "closed"
        if title_key(title) != title_key(job["title"]):
            return None, "title_changed"
        days = age_days(published, now)
        if days is None:
            return None, "posting_date_unverified"
        if days > PROFILE["max_posted_days"]:
            return None, "posted_too_old"
        if not content or len(content) < 70:
            return None, "description_unverified"
        if not location_ok({"location": verified_location}):
            return None, "location_unverified"
        if not commercial_title(title):
            return None, "technical_title"
        mandatory = sum(bool(re.search(pattern, content.lower())) for pattern in HARD_TECHNICAL)
        if mandatory >= 2:
            return None, "mandatory_technical_fit"
        if re.search(r"\b(?:will not|do not|cannot|unable to) (?:provide|offer)?\s*(?:visa )?sponsorship\b", content.lower()):
            return None, "no_sponsorship"
        fresh = dict(job, company=job["company"], title=title, location=verified_location,
                     description=content, posted_age_days=round(days,1),
                     employer_verified=True, verification_source=ats)
        fresh["fit_tier"] = "Strong" if mandatory == 0 and job["prior"] == "new_company" else "Good"
        fresh["fit_reason"] = ("Commercial relationship ownership and growth" if "partnership" in title.lower()
                               else "Commercial account, channel, category or vendor management")
        fresh["gap_reason"] = ("Prior applications at this employer" if job["prior"] == "prior_company"
                              else "No material qualification gap established from automated checks; review required experience")
        return fresh, "verified"
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return None, "verification_failed"


def verify_batch(candidates, now=None, limit=None):
    now = now or datetime.now(timezone.utc)
    limit = limit or PROFILE["max_results"]
    results = []
    counts = Counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for job, outcome in zip(candidates, pool.map(lambda j: verify(j, now=now), candidates)):
            candidate, reason = outcome
            counts[reason] += 1
            if candidate:
                results.append(candidate)
    results.sort(key=lambda j: (0 if j["fit_tier"] == "Strong" else 1, -j["score"], j["posted_age_days"]))
    unique, kept = set(), []
    for job in results:
        name = canon(job["company"])
        if name in unique:
            continue
        unique.add(name)
        kept.append(job)
        if len(kept) >= limit:
            break
    counts["shortlisted"] = len(kept)
    return kept, counts


def build_report(result):
    import html as escape_html
    rows = []
    for j in result["jobs"]:
        def esc(value):
            return escape_html.escape(str(value or ""), quote=True)
        rows.append("<tr><td><a href='{}'>{}</a><div>{}</div></td><td>{}</td><td>{}</td><td>{} days</td><td>{}</td><td>{}</td></tr>".format(
            esc(j["url"]), esc(j["title"]), esc(j["company"]), esc(j["location"]),
            esc(j["fit_tier"]), esc(j["posted_age_days"]), esc(j["fit_reason"]), esc(j["gap_reason"])))
    summary = escape_html.escape(json.dumps(result["counts"], sort_keys=True))
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Verified job search</title>"
            "<style>body{{font-family:Arial,sans-serif;max-width:1050px;margin:auto;color:#1f2937}}td,th{{border-bottom:1px solid #ddd;padding:12px;text-align:left;vertical-align:top}}table{{border-collapse:collapse;width:100%}}a{{color:#185d9b}}</style>"
            "</head><body><h1>Verified commercial jobs</h1><p>Only employer-confirmed jobs with verifiable recent posting dates are shown. "
            "No applications or submissions occurred.</p><p>Scan: {}</p><table><thead><tr><th>Role & employer</th><th>Location</th><th>Tier</th><th>Age</th><th>Fit</th><th>Gap / caveat</th></tr></thead>"
            "<tbody>{}</tbody></table><h2>Screening audit</h2><pre>{}</pre></body></html>".format(
                escape_html.escape(result["generated_at"]), "".join(rows) or "<tr><td colspan='6'>No verified matches found</td></tr>", summary))


def run(args):
    now = datetime.now(timezone.utc)
    applied, tracker = load_applied(args.applied)
    session = requests.Session()
    session.headers.update({"User-Agent":"JobDiscovery/3.0", "Accept":"application/json"})
    candidates, discovery_counts, manifest = discover(
        args.manifest, applied, session=session, now=now,
        hours=args.hours, max_verify=args.verify)
    jobs, validation_counts = verify_batch(candidates, now=now, limit=args.limit)
    counts = dict(discovery_counts)
    counts.update({"verified_" + k:v for k,v in validation_counts.items()})
    result = {"generated_at":now.isoformat(), "feed_updated":manifest.get("last_updated"),
              "tracker_status":tracker, "tracker_rows":len(applied), "counts":counts,
              "jobs":jobs, "top":jobs}
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path(args.html).write_text(build_report(result), encoding="utf-8")
    print(json.dumps({"shortlisted":len(jobs), "counts":counts, "tracker_status":tracker}, indent=2))
    # Don't mask a feed outage as an empty-successful email.
    if discovery_counts["feed_jobs"] < 100:
        raise RuntimeError("Source feed returned too few jobs")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",default=MANIFEST_URL)
    p.add_argument("--applied",default="applied.csv")
    p.add_argument("--output",default="verified_shortlist_v3.json")
    p.add_argument("--html",default="verified_shortlist_v3.html")
    p.add_argument("--hours",type=int,default=PROFILE["age_hours"])
    p.add_argument("--verify",type=int,default=PROFILE["max_verify"])
    p.add_argument("--limit",type=int,default=PROFILE["max_results"])
    args=p.parse_args()
    run(args)

if __name__=="__main__":
    main()
