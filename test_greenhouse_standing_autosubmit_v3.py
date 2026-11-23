"""Standing auto-apply authorization is only valid inside verified workflow runs."""
import os
import unittest
from unittest.mock import patch
from greenhouse_pipeline_v3 import standing_approval

ENV={"AUTO_APPLY_STANDING_APPROVAL":"2026-11-23","GITHUB_EVENT_NAME":"workflow_run",
     "GITHUB_REPOSITORY":"raomahin-rm/scraper","GITHUB_REF":"refs/heads/main"}

def packet():
    return {"version":1,"id":"1111222233334444","company":"Acme","title":"Strategic Partnerships",
            "url":"https://job-boards.greenhouse.io/example/jobs/123",
            "job_fingerprint":"hash","screening":{"decision":"review"},"answers":[],
            "documents":{"resume":{"sha256":"abcdef","path":"/tmp/resume.pdf"}},
            "drafts":{},"missing_required":[],"live_schema":[{"id":"first_name","required":True}],
            "live_review":{"errors":[],"unresolved_live_fields":[]}}

class StandingApplicationAuthorization(unittest.TestCase):
    def test_denies_without_explicit_workflow_context(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):
                standing_approval(packet())
    def test_denies_on_push_event(self):
        with patch.dict(os.environ,{**ENV,"GITHUB_EVENT_NAME":"push"},clear=True):
            with self.assertRaises(ValueError):
                standing_approval(packet())
    def test_denies_missing_question(self):
        p=packet()
        p["missing_required"]=["Non-compete?"]
        with patch.dict(os.environ,ENV,clear=True):
            with self.assertRaises(ValueError):
                standing_approval(p)
    def test_denies_blocked_role(self):
        p=packet()
        p["screening"]["decision"]="blocked"
        with patch.dict(os.environ,ENV,clear=True):
            with self.assertRaises(ValueError):
                standing_approval(p)
    def test_denies_missing_resume(self):
        p=packet()
        p["documents"]={}
        with patch.dict(os.environ,ENV,clear=True):
            with self.assertRaises(ValueError):
                standing_approval(p)
    def test_denies_unresolved_form_fields(self):
        p=packet()
        p["live_review"]["unresolved_live_fields"]=[{"id":"checkbox"}]
        with patch.dict(os.environ,ENV,clear=True):
            with self.assertRaises(ValueError):
                standing_approval(p)
    def test_allows_only_eligible_ready_packet(self):
        p=packet()
        with patch.dict(os.environ,ENV,clear=True):
            approval=standing_approval(p)
        self.assertEqual(approval["actor"],"raomahin-rm")
        self.assertEqual(len(approval["packet_digest"]),64)
        self.assertIn("standing-auto",approval["comment_id"])

if __name__=="__main__":
    unittest.main()
