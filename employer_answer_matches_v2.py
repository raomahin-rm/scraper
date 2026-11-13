"""Create safe, review-only suggestions for questions retrieved from employer APIs.

EEO/demographic answers are never inferred from a resume or stored in GitHub.
Question matches are suggestions, not a completed or submitted form.
"""
import argparse
import json
import re
from pathlib import Path
from application_answers_v2 import draft

SENSITIVE=re.compile(r"\b(gender|sex assigned|race|ethnic|hispanic|latino|veteran|disabilit|sexual orientation|pronouns|transgender)\b",re.I)

def match_application(record,bank):
    results=[]
    for question in record.get("questions",[]):
        label=question.get("label","")
        if SENSITIVE.search(label):
            results.append({"label":label,"required":question.get("required",False),
                            "suggested_answer":None,"category":"voluntary_demographic",
                            "requires_review":True,"reason":"Do not infer or store demographic answers in repository"})
            continue
        suggestion=draft(label,bank)
        results.append({"label":label,"required":question.get("required",False),
                        "fields":question.get("fields",[]),
                        "suggested_answer":suggestion["suggested_answer"],
                        "category":suggestion["category"],"requires_review":True,
                        "reason":suggestion["reason"]})
    return {"id":record["id"],"company":record["company"],"title":record["title"],
            "application_url":record["application_url"],"inspection_status":record["status"],
            "question_matches":results,"submission_approved":False,"submitted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--questions",default="employer_questions_v2.json")
    p.add_argument("--bank",default="application_answers_v2.json")
    p.add_argument("--output",default="employer_answer_matches_v2.json")
    a=p.parse_args()
    records=json.loads(Path(a.questions).read_text(encoding="utf-8"))["applications"]
    bank=json.loads(Path(a.bank).read_text(encoding="utf-8"))
    matches=[match_application(x,bank) for x in records]
    Path(a.output).write_text(json.dumps({"applications":matches},indent=2),encoding="utf-8")
    print("Application reviews:",len(matches))
    print("Question suggestions:",sum(bool(q["suggested_answer"]) for a in matches for q in a["question_matches"]))
    print("Demographic fields flagged:",sum(q["category"]=="voluntary_demographic" for a in matches for q in a["question_matches"]))
    print("Submissions: 0")
if __name__=="__main__":main()
