"""Replacement scraper v2: read-only discovery and normalized job export.

Usage: python scraper_v2.py --limit 80 --output v2_jobs.json
No email, no mutation of seen_jobs.json. Run on development branch only.
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import requests

ROOT = Path(__file__).parent
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref", "source"}

def canonical(url):
    p = urlsplit(url or "")
    q = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING))
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), q, ""))

def endpoint(row):
    kind, slug = row["ats"].lower(), row.get("slug", "")
    if kind == "greenhouse" and slug:
        return "https://boards-api.greenhouse.io/v1/boards/" + slug + "/jobs"
    if kind == "lever" and slug:
        return "https://api.lever.co/v0/postings/" + slug + "?mode=json"
    if kind == "ashby" and slug:
        return "https://api.ashbyhq.com/posting-api/job-board/" + slug
    if kind == "workday" and all(row.get(k) for k in ("tenant", "board", "subdomain")):
        return "https://{}.{}.myworkdayjobs.com/wday/cxs/{}/{}/jobs".format(
            row["tenant"], row["subdomain"], row["tenant"], row["board"])
    return None

def extract(row, data):
    kind = row["ats"].lower()
    if kind == "workday":
        items = data.get("jobPostings", [])
    elif kind == "lever":
        items = data
    else:
        items = data.get("jobs", [])
    if not isinstance(items, list):
        raise ValueError("Invalid job list")
    for item in items:
        if kind == "greenhouse":
            uid = str(item.get("id", ""))
            title = item.get("title", "")
            location = (item.get("location") or {}).get("name", "")
            url = item.get("absolute_url", "")
        elif kind == "lever":
            uid = str(item.get("id", ""))
            title = item.get("text", "")
            location = (item.get("categories") or {}).get("location", "")
            url = item.get("hostedUrl", "")
        elif kind == "ashby":
            uid = str(item.get("id", ""))
            title = item.get("title", "")
            location = item.get("location", "")
            url = item.get("jobUrl", "")
        else:
            uid = str(item.get("bulletFields", [""])[0]) if item.get("bulletFields") else str(item.get("externalPath", ""))
            title = item.get("title", "")
            location = item.get("locationsText") or item.get("locations", "")
            url = "https://{}.{}.myworkdayjobs.com/en-US/{}{}".format(
                row["tenant"], row["subdomain"], row["board"], item.get("externalPath", ""))
        if not isinstance(location, str):
            location = "; ".join(str(x) for x in location)
        if uid and title and url:
            yield {"id": kind + ":" + (row.get("slug") or row.get("tenant", "")) + ":" + uid,
                   "company": row["name"], "title": title, "location": location,
                   "url": canonical(url), "source": kind}

def scan(rows, session, delay=0.4):
    jobs, failures, seen = [], [], set()
    for row in rows:
        url = endpoint(row)
        if not url:
            failures.append({"company": row["name"], "reason": "unconfigured"})
            continue
        try:
            if row["ats"] == "workday":
                response = session.post(url, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}, timeout=20)
            else:
                response = session.get(url, timeout=20)
            response.raise_for_status()
            for job in extract(row, response.json()):
                key = job["id"]
                if key not in seen:
                    seen.add(key)
                    jobs.append(job)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            failures.append({"company": row["name"], "reason": str(exc)[:200]})
        time.sleep(max(0, delay))
    return jobs, failures

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--output", default="v2_jobs.json")
    args = parser.parse_args()
    with (ROOT / "companies.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))[:max(0, args.limit)]
    session = requests.Session()
    session.headers.update({"User-Agent": "PersonalJobDiscovery/2.0", "Accept": "application/json"})
    jobs, failures = scan(rows, session)
    output = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "companies_checked": len(rows), "jobs": jobs, "failures": failures}
    (ROOT / args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("Companies:", len(rows), "Jobs:", len(jobs), "Failures:", len(failures))
if __name__ == "__main__":
    main()
