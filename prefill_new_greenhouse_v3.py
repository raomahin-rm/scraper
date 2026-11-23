"""Create a small isolated worklist of new Greenhouse applications to prefill.

Never changes the durable main queue or submits employer applications.
The existing human approval gate remains required for each eventual submission.
"""
import argparse
import json
from pathlib import Path
from employer_questions_v2 import greenhouse_parts

def select(db, summary, drafts, limit=6):
    ids=[]
    selected={}
    selected_drafts=[]
    indexed={d.get("id"):d for d in drafts.get("drafts",[])}
    for row in summary.get("new_applications",[]):
        if len(ids)>=limit:
            break
        uid=row.get("id")
        app=db["applications"].get(uid)
        if not app or app.get("status")!="draft":
            continue
        if not greenhouse_parts(app.get("url","")):
            continue
        if uid not in indexed:
            continue
        ids.append(uid)
        selected[uid]=app
        selected_drafts.append(indexed[uid])
    return {"version":db.get("version",1),"applications":selected}, {"count":len(selected_drafts),"drafts":selected_drafts}, ids

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",default="applications_v2.json")
    p.add_argument("--summary",default="v3_application_import_summary.json")
    p.add_argument("--drafts",default="tailored_application_drafts_v2.json")
    p.add_argument("--output",default="runtime/source")
    p.add_argument("--max",type=int,default=6)
    a=p.parse_args()
    if a.max<1 or a.max>15:
        p.error("--max must be between 1 and 15")
    db=json.loads(Path(a.queue).read_text())
    summary=json.loads(Path(a.summary).read_text())
    drafts=json.loads(Path(a.drafts).read_text())
    subset, draft_subset, ids=select(db,summary,drafts,a.max)
    out=Path(a.output)
    out.mkdir(parents=True,exist_ok=True)
    (out/"applications_v2.json").write_text(json.dumps(subset,indent=2))
    (out/"tailored_application_drafts_v2.json").write_text(json.dumps(draft_subset,indent=2))
    (out/"greenhouse_ids.json").write_text(json.dumps(ids,indent=2))
    print("New Greenhouse applications selected for non-submitting form preparation:",len(ids))
    if not ids:
        print("No new Greenhouse forms; no employer interaction required")

if __name__=="__main__":
    main()
