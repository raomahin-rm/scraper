"""Regression tests for non-submitting V3 job-to-application queue sync."""
import unittest
from sync_verified_applications_v3 import accept, merge
from application_queue_v2 import identity

def job(company="Example Business",title="Senior Strategic Partnerships Manager",url="https://job-boards.greenhouse.io/example/jobs/123"):
    return {"company":company,"title":title,"url":url,"location":"Chicago, IL",
            "employer_verified":True,"posted_age_days":2,"fit_tier":"Strong",
            "fit_reason":"Commercial relationships","gap_reason":"Review requirements"}

def initial():
    return {"version":1,"applications":{}}

class V3ApplicationBridgeTests(unittest.TestCase):
    def test_imports_verified_greenhouse_as_draft(self):
        db=initial()
        new, counts=merge({"jobs":[job()]},db)
        self.assertEqual(counts["created"],1)
        self.assertEqual(new[0]["status"],"draft")
        self.assertFalse(new[0]["submission_approved"])
        self.assertEqual(new[0]["ats"],"greenhouse")
        self.assertEqual(db["applications"][identity(job())]["status"],"draft")
    def test_unsupported_ats_is_review_not_submit(self):
        db=initial()
        new, counts=merge({"jobs":[job(url="https://jobs.ashbyhq.com/acme/abc-123")]},db)
        self.assertEqual(counts["created"],1)
        self.assertEqual(new[0]["ats"],"manual_review_required")
    def test_existing_queue_and_state_preserved(self):
        db=initial()
        old=job()
        merge({"jobs":[old]},db)
        oldid=identity(old)
        db["applications"][oldid]["status"]="ready_for_review"
        new, counts=merge({"jobs":[old]},db)
        self.assertEqual(counts["existing_id"],1)
        self.assertEqual(db["applications"][oldid]["status"],"ready_for_review")
        self.assertFalse(new)
    def test_similar_role_same_company_is_not_reimported(self):
        db=initial()
        merge({"jobs":[job()]},db)
        new,counts=merge({"jobs":[job(title="Senior Strategic Partnerships Manager",url="https://job-boards.greenhouse.io/example/jobs/124")]},db)
        self.assertEqual(counts["same_employer_similar_title"],1)
        self.assertEqual(len(db["applications"]),1)
        self.assertFalse(new)
    def test_different_job_does_not_block_same_company(self):
        db=initial()
        merge({"jobs":[job()]},db)
        new,counts=merge({"jobs":[job(title="Key Account Manager",url="https://job-boards.greenhouse.io/example/jobs/125")]},db)
        self.assertEqual(counts["created"],1)
    def test_old_unverified_and_weak_roles_excluded(self):
        db=initial()
        base=job()
        for key,val,reason in [
            ("employer_verified",False,"not_employer_verified"),
            ("posted_age_days",None,"posting_age_unknown"),
            ("posted_age_days",31,"not_recent"),
            ("fit_tier","Stretch","weak_fit")
        ]:
            d=dict(base,**{key:val})
            self.assertEqual(accept(d),reason)
            n,_=merge({"jobs":[d]},db)
            self.assertFalse(n)
        self.assertEqual(len(db["applications"]),0)

if __name__=="__main__":
    unittest.main()
