"""Produce employer-linked application review packets; no form submission or guesses.

These are templates, not extracted employer questions. Employer-specific questions
must be collected from the real application page and reviewed separately.
"""
import argparse
import json
from pathlib import Path

FIELDS=("work_authorization","sponsorship","current_status","stem_opt","salary","start_date","relocation","preferred_locations","years_experience","revenue_pnl","enterprise_accounts_contracts","cold_outreach_quota","travel","excluded_companies_roles")

def build_packets(queue,bank):
    packets=[]
    for app in queue["applications"].values():
        if app["status"]=="submitted": continue
        answers={}
        pending=[]
        for field in FIELDS:
            item=bank.get(field,{})
            if isinstance(item,dict) and item.get("approved") and item.get("answer") is not None:
                answers[field]=item["answer"]
            else:
                pending.append(field)
        packets.append({
            "id":app["id"],"company":app["company"],"title":app["title"],
            "location":app["location"],"application_url":app["url"],
            "status":app["status"],"resume":"Commercial Resume (private PDF; not attached)",
            "standard_answers_for_review":answers,"unanswered_standard_fields":pending,
            "employer_specific_questions":"NOT_COLLECTED_REQUIRES_REVIEW",
            "salary_requires_role_specific_review":True,
            "submission_approved":False,"submitted":False,
        })
    return packets

def markdown(packets):
    lines=["# Commercial application review queue","",
           "Draft preparation only. No application forms were accessed or submitted.",
           "Salary and employer-specific questions require individual review.",""]
    for i,p in enumerate(packets,1):
        lines.extend([f"## {i}. {p['company']} — {p['title']}",
          f"- Location: {p['location']}",
          f"- Application: {p['application_url']}",
          f"- Queue ID: \`{p['id']}\`",
          "- Resume: Commercial Resume (attach privately during application)",
          "- Status: DRAFT — approval required",
          "- Missing: "+", ".join(p["unanswered_standard_fields"]),
          "- Employer-specific questions: not yet collected",""])
    return "\n".join(lines)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",default="applications_v2.json")
    p.add_argument("--bank",default="application_answers_v2.json")
    p.add_argument("--output",default="application_review_packets_v2.json")
    p.add_argument("--markdown",default="application_review_packets_v2.md")
    a=p.parse_args()
    queue=json.loads(Path(a.db).read_text(encoding="utf-8"))
    bank=json.loads(Path(a.bank).read_text(encoding="utf-8"))
    packets=build_packets(queue,bank)
    Path(a.output).write_text(json.dumps({"packets":packets,"count":len(packets)},indent=2),encoding="utf-8")
    Path(a.markdown).write_text(markdown(packets),encoding="utf-8")
    print(f"Prepared {len(packets)} review packets; 0 submissions.")
if __name__=="__main__":main()
