import json
import tempfile
import unittest
from pathlib import Path
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
                self.assertEqual(deliver(p/"list.json",p/"history.json",p/"preview.html",True),0)

if __name__=="__main__":
    unittest.main()
