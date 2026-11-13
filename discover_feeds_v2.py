"""Verify alternative ATS boards for currently unconfigured companies.

Read-only: emits suggested changes only after a live jobs endpoint succeeds.
Never silently rewrites companies.csv or treats a guessed slug as verified.
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path
import requests
from scraper_v2 import endpoint

ROOT=Path(__file__).parent

def slug_candidates(name):
    base=re.sub(r"[^a-z0-9]+","",name.casefold())
    candidates=[base]
    if base.endswith("inc"): candidates.append(base[:-3])
    if base.endswith("technologies"): candidates.append(base[:-12])
    return list(dict.fromkeys(x for x in candidates if len(x)>2))

def discover(rows, session, delay=0.15):
    results=[]
    for row in rows:
        if endpoint(row):
            continue
        attempts=0
        found=None
        for slug in slug_candidates(row["name"]):
            for ats in ("greenhouse","ashby","lever"):
                candidate=dict(row,ats=ats,slug=slug)
                url=endpoint(candidate)
                attempts+=1
                try:
                    response=session.get(url,timeout=10)
                    if response.status_code!=200:
                        continue
                    data=response.json()
                    jobs=data if ats=="lever" else data.get("jobs")
                    if not isinstance(jobs,list) or not jobs:
                        continue
                    # Require at least one recognizable posting; no empty boards.
                    if ats=="lever":
                        valid=any(x.get("id") and x.get("text") and x.get("hostedUrl") for x in jobs)
                    elif ats=="greenhouse":
                        valid=any(x.get("id") and x.get("title") and x.get("absolute_url") for x in jobs)
                    else:
                        valid=any(x.get("id") and x.get("title") and x.get("jobUrl") for x in jobs)
                    if valid:
                        found={"name":row["name"],"ats":ats,"slug":slug,"endpoint":url,"jobs":len(jobs),"status":"candidate_verified_endpoint"}
                        break
                except (requests.RequestException,ValueError,TypeError,AttributeError):
                    pass
                finally:
                    time.sleep(max(delay,0))
            if found: break
        results.append(found or {"name":row["name"],"status":"unresolved","attempts":attempts})
    return results

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--limit",type=int,default=305)
    p.add_argument("--output",default="feed_repair_candidates.json")
    args=p.parse_args()
    with (ROOT/"companies.csv").open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))[:args.limit]
    session=requests.Session()
    session.headers.update({"User-Agent":"PersonalJobDiscovery/2.0","Accept":"application/json"})
    result=discover(rows,session)
    (ROOT/args.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("Unconfigured scanned:",len(result),"Live candidate endpoints:",sum(r["status"]=="candidate_verified_endpoint" for r in result))
    for item in result:
        if item["status"]=="candidate_verified_endpoint":
            print(item["name"],item["ats"],item["slug"],item["jobs"])
if __name__=="__main__":
    main()
