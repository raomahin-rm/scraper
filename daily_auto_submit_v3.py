"""Submit complete, previously verified daily-shortlist Greenhouse applications.

Current user authorization (Nov 23 2026) is standing approval for every
shortlisted application. It never authorizes inventing applicant facts, making
privacy/consent choices, bypassing CAPTCHA, or resubmitting uncertain outcomes.
"""
import argparse
import json
import os
import traceback
from collections import Counter
from pathlib import Path
from greenhouse_pipeline_v3 import execute, standing_approval, load

def run(packet_root, summary_path, output):
    root=Path(packet_root)
    public=json.loads(Path(summary_path).read_text(encoding="utf-8"))
    rows=[]
    db_path=root/"applications_v2.json"
    if not db_path.exists():
        raise ValueError("No decrypted application history found")
    candidates=public.get("attempts") or []
    for entry in candidates:
        uid=entry.get("id")
        if not isinstance(uid,str) or not uid.isalnum() or len(uid)!=16:
            continue
        packet_path=root/uid/"packet.json"
        record={"id":uid, "status":"not_ready"}
        if not packet_path.exists():
            record.update(status="no_packet")
            rows.append(record)
            continue
        packet=json.loads(packet_path.read_text(encoding="utf-8"))
        record.update(company=packet.get("company"), title=packet.get("title"))
        try:
            # All risks/required questions are gate-kept before opening browser.
            standing_approval(packet)
            result=execute(packet,db_path,root/uid/"autonomous",submit=True,autonomous=True)
            if result.get("submitted") and result.get("confirmation"):
                record.update(status="confirmed_submitted",confirmation_recorded=True)
            else:
                record.update(status="submission_unknown")
        except Exception as exc:
            status="needs_answers"
            db=load(db_path)
            pipeline_status=db["applications"].get(uid,{}).get("pipeline_status")
            if pipeline_status in {"submission_started","submission_unknown"}:
                status="submission_unknown"
            elif packet.get("screening",{}).get("decision")=="blocked":
                status="blocked"
            elif "Durable journal" in str(exc) or "Prior submission" in str(exc):
                status="prior_attempt_or_duplicate"
            elif "not supported" in str(exc).lower() or "Unsupported" in str(exc):
                status="unsupported"
            record.update(status=status, error_type=type(exc).__name__)
        rows.append(record)
    counts=dict(Counter(row["status"] for row in rows))
    artifact={"applications":rows,"counts":counts,"considered":len(rows),"confirmed_submitted":counts.get("confirmed_submitted",0)}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(artifact,indent=2),encoding="utf-8")
    print("Daily automatic applications:",json.dumps(counts,sort_keys=True))
    return artifact

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--packet-root",default="runtime/greenhouse")
    p.add_argument("--source-summary",default="runtime/source/public-summary.json")
    p.add_argument("--output",default="runtime/greenhouse/auto-submit-public-summary.json")
    a=p.parse_args()
    run(a.packet_root,a.source_summary,a.output)
