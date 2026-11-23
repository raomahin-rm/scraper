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
