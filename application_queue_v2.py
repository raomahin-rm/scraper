"""Application queue for stage 2/3: prepare, approve, track; never auto-submit.

CLI examples:
 python application_queue_v2.py import --shortlist v2_shortlist.json --db applications_v2.json
 python application_queue_v2.py list --db applications_v2.json
 python application_queue_v2.py approve --db applications_v2.json --id <id>
 python application_queue_v2.py submitted --db applications_v2.json --id <id> --confirmation <reference>
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

STATES={"draft","ready_for_review","approved","submitted","rejected","withdrawn"}
TRANSITIONS={
    "draft":{"ready_for_review","rejected"},
    "ready_for_review":{"approved","rejected"},
    "approved":{"submitted","rejected"},
    "submitted":{"withdrawn"},
    "rejected":set(),
    "withdrawn":set(),
}
TRACKING={"utm_source","utm_medium","utm_campaign","utm_content","utm_term","ref","source"}

def canonical(url):
    p=urlsplit(url or "")
    query=urlencode(sorted((k,v) for k,v in parse_qsl(p.query) if k.lower() not in TRACKING))
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/"),query,""))

def identity(job):
    url=canonical(job.get("url",""))
    if not url.startswith("https://"):
        raise ValueError("Job must have a valid HTTPS application URL")
    key="|".join([str(job.get("company","")).strip().casefold(),url])
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def load(path):
    p=Path(path)
    if not p.exists(): return {"version":1,"applications":{}}
    data=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data.get("applications"),dict): raise ValueError("Invalid application database")
    return data

def save(path,data):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+".tmp")
    temp.write_text(json.dumps(data,indent=2,sort_keys=True),encoding="utf-8")
    temp.replace(p)

def import_jobs(data,jobs):
    created=0
    for job in jobs:
        uid=identity(job)
        if uid in data["applications"]: continue
        data["applications"][uid]={
            "id":uid,"company":job.get("company",""),"title":job.get("title",""),
            "location":job.get("location",""),"url":canonical(job.get("url","")),
            "source_id":job.get("id",""),"score":job.get("score"),
            "status":"draft","answers":{},"resume_path":None,
            "confirmation":None,"events":[{"status":"draft","at":datetime.now(timezone.utc).isoformat()}],
        }
        created+=1
    return created

def set_materials(data,uid,resume_path,answers):
    app=data["applications"][uid]
    if app["status"]!="draft": raise ValueError("Only draft applications can be prepared")
    if not resume_path or not isinstance(answers,dict): raise ValueError("Resume and answers object required")
    app["resume_path"]=resume_path
    app["answers"]=answers
    transition(data,uid,"ready_for_review")

def transition(data,uid,status,confirmation=None):
    if status not in STATES: raise ValueError("Unknown status")
    app=data["applications"][uid]
    current=app["status"]
    if status not in TRANSITIONS[current]: raise ValueError(f"Invalid transition: {current} -> {status}")
    if status=="approved" and (not app.get("resume_path") or not isinstance(app.get("answers"),dict)):
        raise ValueError("Review materials before approval")
    if status=="submitted" and not confirmation:
        raise ValueError("Submission confirmation required; never assume a submission succeeded")
    app["status"]=status
    if confirmation: app["confirmation"]=confirmation
    app["events"].append({"status":status,"at":datetime.now(timezone.utc).isoformat()})

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["import","list","prepare","approve","reject","submitted"])
    p.add_argument("--db",default="applications_v2.json")
    p.add_argument("--shortlist",default="v2_shortlist.json")
    p.add_argument("--id")
    p.add_argument("--resume")
    p.add_argument("--answers-json")
    p.add_argument("--confirmation")
    a=p.parse_args()
    db=load(a.db)
    if a.action=="import":
        payload=json.loads(Path(a.shortlist).read_text(encoding="utf-8"))
        print("New applications queued:",import_jobs(db,payload.get("top",[])))
    elif a.action=="list":
        for x in db["applications"].values():
            print(x["id"],x["status"],x["company"],"|",x["title"])
        return
    elif a.action=="prepare":
        if not a.answers_json: p.error("--answers-json required")
        set_materials(db,a.id,a.resume,json.loads(Path(a.answers_json).read_text(encoding="utf-8")))
    else:
        status={"approve":"approved","reject":"rejected","submitted":"submitted"}[a.action]
        transition(db,a.id,status,confirmation=a.confirmation)
    save(a.db,db)

if __name__=="__main__":
    main()
