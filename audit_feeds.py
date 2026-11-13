"""Read-only ATS feed audit. Never sends mail or changes seen_jobs.json."""
import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).parent
FIELDS = ["name", "ats", "status", "http_status", "jobs", "endpoint", "error", "checked_at"]

def endpoint(row):
    ats = row["ats"].lower()
    slug = row.get("slug", "")
    if ats == "greenhouse" and slug:
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    if ats == "lever" and slug:
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if ats == "ashby" and slug:
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    if ats == "workday" and all(row.get(k) for k in ("tenant", "board", "subdomain")):
        tenant, board, sub = (row[k] for k in ("tenant", "board", "subdomain"))
        return f"https://{tenant}.{sub}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
    return None

def check(session, row):
    url = endpoint(row)
    result = dict(name=row["name"], ats=row["ats"], status="not_configured",
                  http_status="", jobs=0, endpoint=url or "", error="",
                  checked_at=datetime.now(timezone.utc).isoformat())
    if not url:
        return result
    try:
        if row["ats"] == "workday":
            response = session.post(url, json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, timeout=15)
        else:
            response = session.get(url, timeout=15)
        result["http_status"] = response.status_code
        response.raise_for_status()
        data = response.json()
        if row["ats"] == "workday":
            jobs = data.get("jobPostings", [])
        elif row["ats"] == "lever":
            jobs = data
        else:
            jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("Unexpected jobs response shape")
        result["jobs"] = len(jobs)
        result["status"] = "verified" if jobs else "reachable_empty"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)[:250]
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--delay", type=float, default=0.4)
    args = parser.parse_args()
    with (ROOT / "companies.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    session = requests.Session()
    session.headers.update({"User-Agent": "PersonalJobFeedAudit/1.0", "Accept": "application/json"})
    results = []
    for row in rows[:max(0, args.limit)]:
        result = check(session, row)
        results.append(result)
        print(f'{result["name"]}: {result["status"]} ({result["http_status"]})', flush=True)
        time.sleep(max(0, args.delay))
    with (ROOT / "feed_audit.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"checked": len(results), "verified": sum(r["status"] == "verified" for r in results),
                      "failed": sum(r["status"] == "failed" for r in results),
                      "unconfigured": sum(r["status"] == "not_configured" for r in results)}))
if __name__ == "__main__":
    main()
