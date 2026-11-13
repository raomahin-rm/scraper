"""Read public Greenhouse application questions without sending applications.

Only recognized Greenhouse job-board URLs are queried. Other ATS platforms are
reported as unsupported, never silently assumed to have no questions.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import requests

GREENHOUSE_HOSTS={"boards.greenhouse.io","job-boards.greenhouse.io","boards.eu.greenhouse.io"}
API="https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?questions=true"

def greenhouse_parts(url):
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in GREENHOUSE_HOSTS:
        return None
    match=re.fullmatch(r"/([A-Za-z0-9_-]+)/jobs/(\d+)/?",p.path)
    return (match.group(1),match.group(2)) if match else None

def extract_questions(payload):
    result=[]
    for q in payload.get("questions",[]):
        fields=q.get("fields") or []
        result.append({"label":q.get("label",""),"required":bool(q.get("required")),
                       "fields":[{"name":f.get("name"),"type":f.get("type"),
                                  "values":f.get("values",[])} for f in fields]})
    return result

def inspect(packet,session=requests):
    parts=greenhouse_parts(packet["application_url"])
    base={"id":packet["id"],"company":packet["company"],"title":packet["title"],
          "application_url":packet["application_url"],"questions":[],"submitted":False}
    if not parts:
        return dict(base,status="manual_review_required",reason="Unsupported ATS or non-standard application URL")
    board,job_id=parts
    try:
        response=session.get(API.format(board=board,job_id=job_id),timeout=15)
        response.raise_for_status()
        questions=extract_questions(response.json())
        return dict(base,status="questions_retrieved",ats="greenhouse",questions=questions,
                    note="Public API questions may not include all dynamically presented form fields")
    except (requests.RequestException,ValueError) as exc:
        return dict(base,status="manual_review_required",reason=str(exc)[:200])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--packets",default="application_review_packets_v2.json")
    p.add_argument("--output",default="employer_questions_v2.json")
    a=p.parse_args()
    packets=json.loads(Path(a.packets).read_text(encoding="utf-8"))["packets"]
    result=[inspect(x) for x in packets]
    Path(a.output).write_text(json.dumps({"applications":result},indent=2),encoding="utf-8")
    print("Greenhouse forms inspected:",sum(x["status"]=="questions_retrieved" for x in result))
    print("Manual review needed:",sum(x["status"]=="manual_review_required" for x in result))
    print("Submissions: 0")
if __name__=="__main__":main()
