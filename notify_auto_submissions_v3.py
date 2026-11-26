"""Email user concise actual employer submission outcomes, never claim drafts are submissions."""
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

def main():
    result=json.loads(Path("runtime/greenhouse/auto-submit-public-summary.json").read_text(encoding="utf-8"))
    rows=result.get("applications",[])
    if not rows:
        print("No new eligible Greenhouse attempts; no application status email.")
        return
    count=result.get("confirmed_submitted",0)
    sender=os.environ["GMAIL_USER"]
    msg=EmailMessage()
    msg["From"]=sender
    msg["To"]=os.environ.get("MAIL_TO") or sender
    msg["Subject"]="Daily applications: {} confirmed submitted / {} checked".format(count,len(rows))
    lines=["CONFIRMED SUBMITTED: {} out of {} Greenhouse candidates.".format(count,len(rows))]
    for row in rows:
        lines.append("{} — {} — {}".format(row.get("company","Unknown company"),
                                               row.get("title","Unknown role"),row.get("status")))
        if row.get("status") in ("needs_answers","blocked"):
            packet_path=Path("runtime/greenhouse")/str(row.get("id",""))/"packet.json"
            if packet_path.is_file():
                try:
                    packet=json.loads(packet_path.read_text(encoding="utf-8"))
                    missing=list(packet.get("missing_required") or [])
                    missing += [x.get("label","") for x in (packet.get("live_review") or {}).get("unresolved_live_fields",[]) if x.get("required")]
                    unique=[]
                    for question in missing:
                        question=" ".join(str(question).strip().rstrip("*").split())
                        if question and question not in unique:
                            unique.append(question)
                    if row.get("status")=="needs_answers" and unique:
                        lines.append("  Pending employer questions (first 4):")
                        for question in unique[:4]:
                            lines.append("  - "+question[:190])
                    if row.get("status")=="blocked":
                        reasons=(packet.get("screening") or {}).get("hard_restrictions") or []
                        lines.append("  Blocked by employer screening; no application sent.")
                        if reasons:
                            lines.append("  "+str(reasons[0])[:190])
                except (ValueError,OSError,TypeError):
                    lines.append("  Employer question details unavailable in this run.")
    lines.append("\nOther ATS platforms are not yet supported by the live submitter.")
    lines.append("Employer application receipt is required for a confirmed submission; pending and unknown outcomes are never treated as success.")
    lines.append("GitHub audit: {}/{}/actions/runs/{}".format(
        os.environ.get("GITHUB_SERVER_URL","https://github.com"),
        os.environ.get("GITHUB_REPOSITORY","raomahin-rm/scraper"),
        os.environ.get("GITHUB_RUN_ID","")))
    msg.set_content("\n".join(lines))
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context()) as smtp:
        smtp.login(sender,os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)
    print("Sent application outcome email:",count,"confirmed out of",len(rows))

if __name__=="__main__":
    main()
