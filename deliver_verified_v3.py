"""Deliver only new employer-verified job results after successful live vetting.

No network except SMTP when --send is explicitly supplied. Never changes
history until SMTP succeeds; an empty shortlist cannot trigger an email.
"""
import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from verified_search_v3 import build_report, canon, title_key

def deliver(shortlist="verified_shortlist_v3.json", history="verified_history_v3.json",
            preview="verified_email_v3.html", send=False, legacy_history="v2_history.json"):
    data=json.loads(Path(shortlist).read_text(encoding="utf-8"))
    seen={}
    if Path(history).exists():
        seen=json.loads(Path(history).read_text(encoding="utf-8"))
        if not isinstance(seen,dict):
            raise ValueError("History must be a dictionary")
    legacy={}
    if Path(legacy_history).exists():
        old=json.loads(Path(legacy_history).read_text(encoding="utf-8"))
        if isinstance(old,dict):
            legacy={(canon(entry.get("company")),title_key(entry.get("title"))) for entry in old.values() if isinstance(entry,dict)}
    today = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    last_report = seen.get("__daily_report__", {})
    if last_report.get("local_date") == today:
        print("Daily report already emailed for", today, "; skipping duplicate")
        Path(preview).write_text(build_report(dict(data,jobs=[])),encoding="utf-8")
        return 0
    available=[j for j in data.get("jobs",[]) if j.get("employer_verified") and
               j.get("posted_age_days") is not None and
               j.get("url") not in seen and
               (canon(j.get("company")),title_key(j.get("title"))) not in legacy and
               j.get("fit_tier") in ("Strong","Good")]
    if len(data.get("jobs",[])) > 0 and len(available) == 0:
        print("No new verified jobs to email.")
    report=dict(data,jobs=available)
    html_body=build_report(report)
    Path(preview).write_text(html_body,encoding="utf-8")
    print("Verified new roles:",len(available),"send:",send)
    if not send:
        print("Preview only; no email sent or history changed.")
        return len(available)
    user=os.environ["GMAIL_USER"]
    password=os.environ["GMAIL_APP_PASSWORD"]
    recipient=os.environ.get("MAIL_TO") or user
    msg=EmailMessage()
    if available:
        msg["Subject"]="Verified job shortlist: {} new commercial matches".format(len(available))
        msg.set_content("\n".join("{} — {} — {} days old — {}".format(j["company"],j["title"],j["posted_age_days"],j["url"]) for j in available))
        msg.add_alternative(html_body,subtype="html")
    else:
        msg["Subject"]="Verified job search: No new qualifying roles today"
        msg.set_content("The daily job search completed. There were no new employer-verified, qualifying roles that had not already been sent. This is a successful run, not a delivery failure.")
    msg["From"]=user
    msg["To"]=recipient
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context()) as smtp:
        smtp.login(user,password)
        smtp.send_message(msg)
    stamp=datetime.now(timezone.utc).isoformat()
    for j in available:
        seen[j["url"]]={"company":j["company"],"title":j["title"],"emailed_at":stamp}
    seen["__daily_report__"]={"local_date":today,"sent_at":stamp,"matches":len(available)}
    temp=Path(str(history)+".tmp")
    temp.write_text(json.dumps(seen,indent=2),encoding="utf-8")
    temp.replace(history)
    print("Daily email delivered and history saved:",len(available),"jobs for",today)
    return len(available)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shortlist",default="verified_shortlist_v3.json")
    p.add_argument("--history",default="verified_history_v3.json")
    p.add_argument("--preview",default="verified_email_v3.html")
    p.add_argument("--send",action="store_true")
    p.add_argument("--legacy-history",default="v2_history.json")
    a=p.parse_args()
    deliver(a.shortlist,a.history,a.preview,a.send,a.legacy_history)

if __name__=="__main__":
    main()
