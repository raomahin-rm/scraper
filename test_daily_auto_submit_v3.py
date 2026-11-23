"""Validate daily autonomous runner without contacting employer sites."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from daily_auto_submit_v3 import run

def packet(uid):
    return {"id":uid,"company":"Acme","title":"Strategic Partnerships Manager",
            "screening":{"decision":"review"},"missing_required":[]}

class AutonomousRunnerTests(unittest.TestCase):
    def setup(self,p,uid="abcd1234abcd1234"):
        root=p/"greenhouse"
        (root/uid).mkdir(parents=True)
        (root/uid/"packet.json").write_text(json.dumps(packet(uid)))
        (root/"applications_v2.json").write_text(json.dumps({"version":1,"applications":{uid:{"status":"draft","events":[]}}}))
        (p/"summary.json").write_text(json.dumps({"attempts":[{"id":uid,"status":"ready_for_review"}]}))
        return root,uid
    def test_confirmed_submission_must_have_employer_receipt(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);root,uid=self.setup(p)
            with patch("daily_auto_submit_v3.standing_approval",return_value={"packet_digest":"abc"}),patch("daily_auto_submit_v3.execute",return_value={"submitted":True,"confirmation":"Employer received"}):
                result=run(root,p/"summary.json",p/"out.json")
            self.assertEqual(result["confirmed_submitted"],1)
            self.assertEqual(result["applications"][0]["status"],"confirmed_submitted")
    def test_missing_confirmation_is_unknown_not_success(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);root,uid=self.setup(p)
            with patch("daily_auto_submit_v3.standing_approval",return_value={}),patch("daily_auto_submit_v3.execute",return_value={"submitted":True}):
                result=run(root,p/"summary.json",p/"out.json")
            self.assertEqual(result["confirmed_submitted"],0)
            self.assertEqual(result["applications"][0]["status"],"submission_unknown")
    def test_missing_answers_block_before_browser(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);root,uid=self.setup(p)
            with patch("daily_auto_submit_v3.standing_approval",side_effect=ValueError("missing fields")),patch("daily_auto_submit_v3.execute") as submit:
                result=run(root,p/"summary.json",p/"out.json")
            self.assertEqual(result["applications"][0]["status"],"needs_answers")
            submit.assert_not_called()
if __name__=="__main__":
    unittest.main()
