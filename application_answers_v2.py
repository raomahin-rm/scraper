"""Match approved standard answers to employer questions; never guess or submit."""
import json
import re
from pathlib import Path

RULES = {
 "work_authorization": [r"authorized to work",r"legally (?:eligible|permitted) to work",r"right to work"],
 "sponsorship": [r"(?:require|need).{0,40}sponsorship",r"(?:visa|immigration) sponsorship",r"sponsor.{0,30}(?:now|future)"],
 "salary": [r"salary expectation",r"desired (?:salary|compensation|pay)",r"compensation expectation"],
 "relocation": [r"willing to relocate",r"open to relocat",r"relocation preference"],
 "start_date": [r"earliest (?:start|availability)",r"when can you start",r"available to start"],
 "years_experience": [r"how many years",r"years of (?:relevant )?experience"],
}
# Answer bank is opt-in. Empty answers always require user review.
def load_bank(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValueError("Answer bank must be an object")
    return data

def classify(question):
    q=re.sub(r"\s+"," ",question.strip().lower())
    hits=[name for name,patterns in RULES.items() if any(re.search(p,q) for p in patterns)]
    # Sponsorship takes precedence over general authorization wording.
    if "sponsorship" in hits: return "sponsorship"
    return hits[0] if len(hits)==1 else None

def draft(question,bank):
    key=classify(question)
    item=bank.get(key,{}) if key else {}
    answer=item.get("answer") if isinstance(item,dict) else None
    approved=item.get("approved",False) if isinstance(item,dict) else False
    # User-provided answers are suggestions, not authorization to submit.
    return {"question":question,"category":key,"suggested_answer":answer if approved and answer else None,
            "requires_review":True,"reason":"approved_answer_for_review" if approved and answer else "missing_or_unapproved_answer"}

def draft_all(questions,bank):
    return [draft(q,bank) for q in questions]

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--questions",required=True,help="JSON array of employer questions")
    p.add_argument("--bank",default="application_answers_v2.json")
    p.add_argument("--output",default="application_answer_drafts.json")
    a=p.parse_args()
    questions=json.loads(Path(a.questions).read_text(encoding="utf-8"))
    if not isinstance(questions,list) or not all(isinstance(q,str) for q in questions):
        raise ValueError("Questions must be a JSON array of strings")
    Path(a.output).write_text(json.dumps(draft_all(questions,load_bank(a.bank)),indent=2),encoding="utf-8")
