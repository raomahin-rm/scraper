"""Notify the candidate about newly drafted application packets, not submissions."""
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

def main():
    summary=json.loads(Path("v3_application_import_summary.json").read_text(encoding="utf-8"))
    new=summary.get("new_applications",[])
    if not new:
        print("No newly prepared applications; no duplicate review email.")
        return
    sender=os.environ["GMAIL_USER"]
    recipient=os.environ.get("MAIL_TO") or sender
    url="{}/{}/actions/runs/{}".format(
        os.environ.get("GITHUB_SERVER_URL","https://github.com"),
        os.environ.get("GITHUB_REPOSITORY","raomahin-rm/scraper"),
        os.environ.get("GITHUB_RUN_ID",""))
    msg=EmailMessage()
    msg["From"]=sender
    msg["To"]=recipient
    msg["Subject"]="Application drafts ready for review: {} new jobs (0 submitted)".format(len(new))
    rows=["{} — {} — {} — {}".format(x["company"],x["title"],x["ats"],x["url"]) for x in new]
    msg.set_content(
        "The job discovery workflow has imported {} new employer-verified leads into your application review queue.\n\n".format(len(new))+
        "\n".join(rows)+
        "\n\nJob forms and employer-specific answers require individual review. Zero applications were submitted.\n"+
        "Review the prepared packets and related action artifact here: "+url+
        "\n\nThe existing per-application submission approval requirement remains in place."
    )
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context()) as smtp:
        smtp.login(sender,os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)
    print("Application draft notification sent for",len(new),"new queue items")

if __name__=="__main__":
    main()
