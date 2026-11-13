"""Replacement v2 delivery: explicit opt-in only, history updated after SMTP success."""
import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from email_preview_v2 import render
from history_v2 import load_history, new_jobs, mark_delivered, save_history

def prepare(shortlist, history, limit=40):
    pending = new_jobs(shortlist.get("top", []), history)[:limit]
    payload = dict(shortlist, top=pending)
    return pending, render(payload)

def deliver(shortlist_path="v2_shortlist.json", history_path="v2_history.json",
            preview_path="v2_pending_preview.html", send=False):
    shortlist = json.loads(Path(shortlist_path).read_text(encoding="utf-8"))
    history = load_history(history_path)
    pending, html_body = prepare(shortlist, history)
    Path(preview_path).write_text(html_body, encoding="utf-8")
    print("Pending new jobs:", len(pending), "Preview:", preview_path)
    if not send:
        print("DRY RUN: no email sent; history unchanged")
        return len(pending)
    if not pending:
        print("No new jobs; no email sent; history unchanged")
        return 0
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.getenv("MAIL_TO") or user
    msg = EmailMessage()
    msg["Subject"] = f"Job shortlist: {len(pending)} new opportunities"
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(f"{len(pending)} new jobs. Open this email in HTML mode for application links.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    save_history(history_path, mark_delivered(pending, history))
    print("Email sent; history saved:", len(pending))
    return len(pending)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="v2_shortlist.json")
    p.add_argument("--history", default="v2_history.json")
    p.add_argument("--preview", default="v2_pending_preview.html")
    p.add_argument("--send", action="store_true", help="Explicitly enable SMTP delivery")
    a = p.parse_args()
    deliver(a.input, a.history, a.preview, a.send)
