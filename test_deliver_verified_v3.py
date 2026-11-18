import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock
from unittest.mock import patch
from deliver_verified_v3 import deliver

class DeliveryTests(unittest.TestCase):
    def test_only_verified_unsent_roles(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            data={"generated_at":"2026-11-15","counts":{},"jobs":[
                {"url":"https://example.com/a","title":"Partnerships Manager","company":"A","location":"Chicago",
                 "employer_verified":True,"posted_age_days":2,"fit_tier":"Strong",
                 "fit_reason":"B2B","gap_reason":"None"},
                {"url":"https://example.com/b","title":"Partnerships Manager","company":"B","location":"Chicago",
                 "employer_verified":False,"posted_age_days":2,"fit_tier":"Strong",
                 "fit_reason":"B2B","gap_reason":"None"}]}
            (p/"list.json").write_text(json.dumps(data))
            (p/"history.json").write_text("{}")
            with patch.dict("os.environ",{},clear=True):
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",False),1)
            self.assertIn("Partnerships Manager",(p/"preview.html").read_text())
            self.assertEqual(json.loads((p/"history.json").read_text()),{})
    def test_applied_history_skips_all(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"list.json").write_text(json.dumps({"generated_at":"2026-11-15","counts":{},"jobs":[
                {"url":"https://example.com/a","title":"Manager","company":"A","location":"Chicago","employer_verified":True,
                 "posted_age_days":2,"fit_tier":"Good","fit_reason":"B2B","gap_reason":"None"}]}))
            (p/"history.json").write_text(json.dumps({"https://example.com/a":{"emailed_at":"yesterday"}}))
            with patch.dict("os.environ",{},clear=True):
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",False),0)

    def test_empty_daily_report_sends_status_and_prevents_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"list.json").write_text(json.dumps({"generated_at":"2026-11-18","counts":{},"jobs":[]}))
            smtp=MagicMock()
            smtp.__enter__.return_value=smtp
            with patch.dict("os.environ",{"GMAIL_USER":"sender@example.com","GMAIL_APP_PASSWORD":"fake","MAIL_TO":"receiver@example.com"},clear=True), patch("deliver_verified_v3.smtplib.SMTP_SSL", return_value=smtp):
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",True),0)
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",True),0)
            self.assertEqual(smtp.send_message.call_count,1)
            msg=smtp.send_message.call_args.args[0]
            self.assertIn("No new qualifying roles today",msg["Subject"])
            hist=json.loads((p/"history.json").read_text())
            self.assertEqual(hist["__daily_report__"]["local_date"],datetime.now(ZoneInfo("America/Chicago")).date().isoformat())
    def test_nonempty_report_sends_one_email_and_records_history(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"list.json").write_text(json.dumps({"generated_at":"2026-11-18","counts":{},"jobs":[{"url":"https://example.com/xyz","company":"Test Employer","title":"Strategic Partnerships Manager","location":"Chicago","employer_verified":True,"posted_age_days":1,"fit_tier":"Strong","fit_reason":"Commercial","gap_reason":"Review"}]}))
            smtp=MagicMock()
            smtp.__enter__.return_value=smtp
            with patch.dict("os.environ",{"GMAIL_USER":"sender@example.com","GMAIL_APP_PASSWORD":"fake","MAIL_TO":"receiver@example.com"},clear=True), patch("deliver_verified_v3.smtplib.SMTP_SSL",return_value=smtp):
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",True),1)
            hist=json.loads((p/"history.json").read_text())
            self.assertIn("https://example.com/xyz",hist)
            self.assertEqual(hist["__daily_report__"]["matches"],1)

if __name__=="__main__":
    unittest.main()
