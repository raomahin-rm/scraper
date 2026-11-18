"""Send a clear failure notification if the scheduled V3 workflow breaks."""
import os
import smtplib
import ssl
from email.message import EmailMessage

def main():
    user=os.environ["GMAIL_USER"]
    password=os.environ["GMAIL_APP_PASSWORD"]
    recipient=os.environ.get("MAIL_TO") or user
    url="{}/{}/actions/runs/{}".format(os.environ.get("GITHUB_SERVER_URL","https://github.com"),
                                       os.environ.get("GITHUB_REPOSITORY","raomahin-rm/scraper"),
                                       os.environ.get("GITHUB_RUN_ID","unknown"))
    msg=EmailMessage()
    msg["Subject"]="JOB SEARCH ALERT: Daily V3 run failed"
    msg["From"]=user
    msg["To"]=recipient
    msg.set_content("The verified job-search run failed before completing today's delivery.\n"+
                    "This is a failure alert, not a report of zero eligible jobs.\n"+
                    "Inspect the run and fix the broken step: "+url)
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context()) as smtp:
        smtp.login(user,password)
        smtp.send_message(msg)
    print("Failure notification dispatched")
if __name__=="__main__":
    main()
