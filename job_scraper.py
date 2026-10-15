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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

import config

ROOT = Path(__file__).parent
SEEN_FILE = ROOT / "seen_jobs.json"
APPLIED_FILE = ROOT / "applied.csv"
HEADERS = {"User-Agent": "personal-job-scraper/1.0 (personal use)"}
TIMEOUT = 25
NOW = datetime.now(timezone.utc)


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
    fit: int | None = None
    reason: str = ""
    flags: str = ""
    final: float = 0.0


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
            company=j.get("company_name") or slug.title(),
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
            company=slug.title(),
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
            company=slug.title(),
            title=j.get("title", ""),
            location=loc,
            url=j.get("jobUrl", ""),
            posted=parse_iso(j.get("publishedAt")),
            description=j.get("descriptionPlain") or clean(j.get("descriptionHtml")),
        )


def fetch_adzuna():
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("adzuna: no keys set, skipping")
        return
    for query in config.ADZUNA_QUERIES:
        for where in config.ADZUNA_LOCATIONS:
            data = get_json(
                "https://api.adzuna.com/v1/api/jobs/us/search/1",
                {
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": query,
                    "where": where,
                    "results_per_page": 30,
                    "max_days_old": 2,
                    "sort_by": "date",
                    "content-type": "application/json",
                },
            )
            for j in data.get("results", []):
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


def fetch_all():
    jobs, errors = [], []
    plan = (
        [("greenhouse", s, fetch_greenhouse) for s in config.GREENHOUSE]
        + [("lever", s, fetch_lever) for s in config.LEVER]
        + [("ashby", s, fetch_ashby) for s in config.ASHBY]
    )
    for kind, slug, fn in plan:
        try:
            got = list(fn(slug))
            print(f"{kind}/{slug}: {len(got)} jobs")
            jobs += got
        except Exception as e:  # keep going if one company fails
            errors.append(f"{kind}/{slug}: {e}")
            print(f"{kind}/{slug}: FAILED {e}")
        time.sleep(0.3)
    try:
        got = list(fetch_adzuna())
        print(f"adzuna: {len(got)} jobs")
        jobs += got
    except Exception as e:
        errors.append(f"adzuna: {e}")
        print(f"adzuna: FAILED {e}")
    return jobs, errors


# ---------------------------------------------------------------------------
# Filtering and scoring
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


def location_points(loc):
    l = loc.lower()
    if re.search(r"\b(emea|apac|latam|uk|united kingdom|india|germany|singapore)\b", l):
        return 0
    for place in config.PREFERRED_LOCATIONS:
        if place in l:
            return 10 if place == "remote" else 15
    return 0


def rule_score(job):
    t = job.title.lower()
    d = job.description.lower()
    flags = []

    s = config.TRACKS[job.track]["weight"]
    if re.search(r"\b(senior|sr\.?|lead|manager)\b", t):
        s += 10
    s += location_points(job.location)
    if job.source in ("greenhouse", "lever", "ashby"):
        s += 10  # on your company watchlist

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
        elif top <= 3:
            s -= 15
            flags.append("looks junior")

    job.score = s
    job.flags = "; ".join(flags)
    job.resume = pick_resume(job)


def pick_resume(job):
    if job.track == "policy":
        return "Policy"
    d = job.description.lower()
    tech = re.search(
        r"\b(saas|artificial intelligence|machine learning|startup|marketplace|fintech|platform)\b", d
    )
    if job.source in ("greenhouse", "lever", "ashby") or tech:
        return "Tech/AI"
    return "Base"


def shortlist(jobs, seen, applied):
    cutoff = NOW - timedelta(hours=config.MAX_AGE_HOURS)
    stats = dict(fetched=len(jobs), stale=0, title=0, seen=0, applied=0, dupe=0, low=0)
    out, keys = [], set()
    for j in jobs:
        if not j.url or not j.title:
            continue
        if j.posted and j.posted < cutoff:
            stats["stale"] += 1
            continue
        track = track_for(j.title)
        if not track or title_blocked(j.title):
            stats["title"] += 1
            continue
        if j.uid in seen:
            stats["seen"] += 1
            continue
        if (norm(j.company), norm(j.title)) in applied or j.url in applied:
            stats["applied"] += 1
            continue
        key = (norm(j.company), norm(j.title), norm(j.location))
        if key in keys:
            stats["dupe"] += 1
            continue
        keys.add(key)
        j.track = track
        rule_score(j)
        if j.score < config.MIN_SCORE:
            stats["low"] += 1
            continue
        out.append(j)
    out.sort(key=lambda x: x.score, reverse=True)
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
        "should score between 4 and 7. Only give 9 or 10 for a near-perfect match.\n\n"
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


def rank(pool):
    """Review the top of the pool with the LLM (if a key is set) and rank."""
    pool = pool[: config.LLM_POOL]
    if not os.getenv("ANTHROPIC_API_KEY"):
        for j in pool:
            j.final = j.score
        return pool[: config.TOP_N], pool
    for j in pool:
        llm_review(j)
        time.sleep(0.3)
    kept = [j for j in pool if j.fit is None or j.fit >= config.MIN_FIT]
    for j in kept:
        j.final = j.score + (j.fit or 5) * 8
    kept.sort(key=lambda x: x.final, reverse=True)
    return kept[: config.TOP_N], pool


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
TRACK_LABEL = {k: v["label"] for k, v in config.TRACKS.items()}


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
        rows.append(
            "<tr>"
            f"<td>{i}</td><td>{fit}</td>"
            f'<td><a href="{esc(j.url)}">{esc(j.title)}</a><br>'
            f'<span style="color:#555">{esc(j.company)}</span></td>'
            f"<td>{esc(j.location)[:40]}</td>"
            f"<td>{esc(TRACK_LABEL.get(j.track, j.track))}</td>"
            f"<td>{esc(j.resume)}</td><td>{age_text(j)}</td><td>{note}</td>"
            "</tr>"
        )
    table = (
        '<table cellpadding="6" cellspacing="0" border="1" '
        'style="border-collapse:collapse;border-color:#ddd;font-size:13px">'
        "<tr style='background:#f3f4f6'><th>#</th><th>Fit</th><th>Role</th>"
        "<th>Where</th><th>Track</th><th>Resume</th><th>Age</th><th>Notes</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    footer = (
        f"<p style='color:#666;font-size:12px'>Scanned {stats['fetched']} jobs. "
        f"Dropped: {stats['stale']} old, {stats['title']} wrong title or level, "
        f"{stats['seen']} already sent, {stats['applied']} already applied, "
        f"{stats['dupe']} duplicates, {stats['low']} low score.</p>"
    )
    if errors:
        footer += (
            "<p style='color:#b91c1c;font-size:12px'>Sources that failed "
            "(fix the slug in config.py or delete it):<br>"
            + "<br>".join(esc(e) for e in errors)
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
    w.writerow(["final", "fit", "track", "resume", "company", "title",
                "location", "posted", "url", "reason", "flags"])
    for j in jobs:
        w.writerow([
            round(j.final, 1), j.fit or "", TRACK_LABEL.get(j.track, j.track),
            j.resume, j.company, j.title, j.location,
            j.posted.isoformat() if j.posted else "", j.url, j.reason, j.flags,
        ])
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
    cutoff = (NOW - timedelta(days=90)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_FILE.write_text(json.dumps(seen, indent=0))


def load_applied():
    """applied.csv columns: company,title,url (title and url are optional)."""
    out = set()
    if APPLIED_FILE.exists():
        with open(APPLIED_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("url"):
                    out.add(row["url"].strip())
                if row.get("company") and row.get("title"):
                    out.add((norm(row["company"]), norm(row["title"])))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(jobs, errors, seen, applied):
    pool, stats = shortlist(jobs, seen, applied)
    top, reviewed = rank(pool)
    return top, reviewed, stats


def main():
    dry = "--dry-run" in sys.argv
    seen, applied = load_seen(), load_applied()
    jobs, errors = fetch_all()
    top, reviewed, stats = run(jobs, errors, seen, applied)
    body, text = build_email(top, stats, errors)
    local = NOW.astimezone(ZoneInfo("America/Chicago"))
    subject = f"{len(top)} new roles for you, {local:%a %b %d}"

    if dry:
        (ROOT / "preview.html").write_text(body, encoding="utf-8")
        print(f"Dry run: {len(top)} roles. Wrote preview.html")
        return

    send_email(subject, body, text, build_csv(top))
    for j in reviewed:
        seen[j.uid] = NOW.isoformat()
    save_seen(seen)
    print(f"Sent {len(top)} roles.")


if __name__ == "__main__":
    main()
