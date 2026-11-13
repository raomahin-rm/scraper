"""Prepare company-specific motivation and optional cover-letter drafts for review.

Uses only approved non-sensitive commercial achievements and the job title/company.
No employer research is invented; generated text is a starting draft, not a submission.
"""
import argparse
import json
from pathlib import Path

EVIDENCE=[
    "negotiating supplier agreements and improving working capital at Leverify",
    "building enterprise sales pipelines and driving acquisition growth at Retailo",
    "managing a commercial portfolio and strategic customer relationships at Packages Limited",
]

def prepare(packet):
    company=packet["company"].strip()
    title=packet["title"].strip()
    if not company or not title: raise ValueError("Company and title are required")
    motivation=(f"I'm interested in the {title} opportunity at {company} because it offers "
        "a chance to apply my experience in commercial strategy, strategic partnerships, "
        "enterprise account growth, and cross-functional execution. My background includes "
        f"{EVIDENCE[0]} and {EVIDENCE[1]}. "
        "I'd welcome the opportunity to learn more about the team's priorities and "
        "how I could contribute.")
    letter=(f"Dear {company} Hiring Team,\n\n"
        f"I'm writing to express my interest in the {title} position. "
        "I bring ten years of professional experience spanning commercial strategy, "
        "business development, partnerships, and category management across e-commerce, "
        "technology, and consumer businesses. My experience includes "
        f"{EVIDENCE[0]}, {EVIDENCE[1]}, and {EVIDENCE[2]}.\n\n"
        "I would welcome the opportunity to discuss how this background aligns with "
        f"the {title} role and your team's objectives.\n\n"
        "Sincerely,\nRao Mahin")
    # Letter layout follows the user's Faire reference; personal contact details stay private.
    letter_layout={
        "sender_name":"Rao Mahin",
        "sender_contact":"PRIVATE_CONTACT_DETAILS_INSERT_AT_FINAL_RENDER",
        "date_alignment":"right",
        "date":"CURRENT_DATE_AT_RENDER",
        "recipient":"Hiring Manager / company team (verify employer address)",
        "subject":f"Application for {title}",
        "salutation":f"Dear {company} Hiring Team,",
        "closing":"Best regards,\\nRao Mahin",
        "format_reference":"Faire letter: sender top-left, date right, recipient, salutation, body, closing",
    }
    # Cover letters are optional by default, not mandatory for all 40 applications.
    # Only required or demonstrably high-value optional letters should be finalized.
    cover_letter_decision="review_requirement_and_role_fit"
    return {"id":packet["id"],"company":company,"title":title,
            "application_url":packet["application_url"],
            "why_company_draft":motivation,"optional_cover_letter_draft":letter,"cover_letter_decision":cover_letter_decision,"cover_letter_layout":letter_layout,
            "company_specific_research_verified":False,
            "note":"Tailored to company name and role; validate job requirements and employer priorities before approval.",
            "salary_guidance":"If a verified published base salary range exceeds the baseline, propose its midpoint for user review; otherwise review individually.",
            "relocation_assistance":"Preferred but not required",
            "sms_recruiter_contact":"Yes",
            "ai_use_question":"Flag for individual review; answer truthfully",
            "future_opportunities_opt_in":"Yes, subject to employer-specific consent wording",
            "demographic_questions":"Individual review; do not infer or auto-fill",
            "submission_approved":False,"submitted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--packets",default="application_review_packets_v2.json")
    p.add_argument("--output",default="tailored_application_drafts_v2.json")
    a=p.parse_args()
    packets=json.loads(Path(a.packets).read_text(encoding="utf-8"))["packets"]
    result=[prepare(x) for x in packets]
    Path(a.output).write_text(json.dumps({"drafts":result,"count":len(result)},indent=2),encoding="utf-8")
    print("Tailored motivation and cover-letter drafts:",len(result))
    print("Submissions: 0")
if __name__=="__main__":main()
