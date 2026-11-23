"""Bring employer-verified V3 jobs into the persistent application review queue.

This is discovery -> DRAFT preparation, never approval or submission.
Existing status/history is preserved. Conservative near-duplicate screening
protects against repeat submissions, including unresolved earlier attempts.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from application_queue_v2 import identity, import_jobs, load, save, canonical
from employer_questions_v2 import greenhouse_parts


def norm(text):
    return re.sub(r"\W+", " ", str(text or "").casefold()).strip()


def near_identical(a, b):
    if norm(a.get("company")) != norm(b.get("company")):
        return False
    atitle, btitle = norm(a.get("title")), norm(b.get("title"))
    return bool(atitle and btitle and (
        atitle == btitle or
        (min(len(atitle), len(btitle)) >= 24 and (atitle in btitle or btitle in atitle))
    ))


def accept(job):
    if not isinstance(job, dict):
        return "invalid_record"
    if job.get("employer_verified") is not True:
        return "not_employer_verified"
    try:
        age = float(job.get("posted_age_days"))
    except (TypeError, ValueError):
        return "posting_age_unknown"
    if not 0 <= age <= 21:
        return "not_recent"
    if job.get("fit_tier") not in ("Strong", "Good"):
        return "weak_fit"
    if not all(isinstance(job.get(f), str) and job[f].strip() for f in ("company", "title", "url")):
        return "missing_fields"
    if not job["url"].startswith("https://"):
        return "not_https"
    return "eligible"


def merge(shortlist, db, max_jobs=15):
    stats = Counter()
    new = []
    candidates = shortlist.get("jobs") or shortlist.get("top") or []
    if not isinstance(candidates, list):
        raise ValueError("Shortlist jobs must be a list")
    for job in candidates[:max_jobs]:
        reason = accept(job)
        if reason != "eligible":
            stats[reason] += 1
            continue
        uid = identity(job)
        if uid in db["applications"]:
            stats["existing_id"] += 1
            continue
        if any(near_identical(job, existing) for existing in db["applications"].values()):
            stats["same_employer_similar_title"] += 1
            continue
        created = import_jobs(db, [job])
        if not created:
            stats["not_imported"] += 1
            continue
        app = db["applications"][uid]
        app["employer_verified"] = True
        app["employer_posted_age_days_at_discovery"] = job["posted_age_days"]
        app["discovery_source"] = "verified_search_v3"
        app["ats"] = "greenhouse" if greenhouse_parts(job["url"]) else "manual_review_required"
        app["fit_tier"] = job["fit_tier"]
        app["fit_reason"] = job.get("fit_reason", "")
        app["gap_reason"] = job.get("gap_reason", "")
        new.append({"id":uid, "company":app["company"], "title":app["title"],
                    "location":app["location"], "url":app["url"],
                    "ats":app["ats"], "status":"draft", "submission_approved":False})
        stats["created"] += 1
    stats["previous_total_in_queue"] = len(db["applications"]) - len(new)
    stats["total_in_queue"] = len(db["applications"])
    stats["new_automatic_greenhouse_preparation_candidates"] = sum(x["ats"] == "greenhouse" for x in new)
    stats["new_manual_ats_review_candidates"] = len(new) - stats["new_automatic_greenhouse_preparation_candidates"]
    return new, dict(stats)


def run(args):
    source = json.loads(Path(args.shortlist).read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("Invalid shortlisted source")
    db = load(args.db)
    if not Path(args.db).is_file() or not db["applications"]:
        raise ValueError("Prior application queue missing or empty; refusing to reset it")
    new, counters = merge(source, db, max_jobs=args.limit)
    save(args.db, db)
    output = {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_run_id":args.source_run_id,
        "new_applications":new, "counts":counters,
        "submitted":0,
        "message":"Drafts queued for individual review only; zero employer applications submitted.",
    }
    Path(args.output).write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(json.dumps(counters,indent=2))
    print("Employer submissions: 0")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shortlist",default="verified_shortlist_v3.json")
    p.add_argument("--db",default="applications_v2.json")
    p.add_argument("--output",default="v3_application_import_summary.json")
    p.add_argument("--limit",type=int,default=15)
    p.add_argument("--source-run-id",default="")
    args=p.parse_args()
    run(args)


if __name__=="__main__":
    main()
