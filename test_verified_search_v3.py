"""Offline regression tests for the v3 sourcing, verification and vetting pipeline."""
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
import verified_search_v3 as v3

NOW=datetime(2026,11,15,20,0,tzinfo=timezone.utc)

def lead(title="Strategic Partnerships Manager", company="Fresh Employer", ats="Greenhouse", url=None):
    return {
        "company":company, "title":title, "ats":ats,
        "location":"Chicago, IL",
        "url":url or "https://job-boards.greenhouse.io/freshemployer/jobs/123",
        "first_seen":NOW.isoformat(),
    }

def response(value, status=200):
    r=Mock()
    r.status_code=status
    r.json.return_value=value
    r.raise_for_status.return_value=None
    return r

def greenhouse(title="Strategic Partnerships Manager", when="2026-11-13T00:00:00Z"):
    return {"title":title, "first_published":when,
            "location":{"name":"Chicago, IL"},
            "content":"Own enterprise partnerships, negotiate commercial agreements, build revenue programs, manage accounts and partner channel growth for major customers."}

class DiscoveryTests(unittest.TestCase):
    def test_recent_candidate(self):
        self.assertEqual(v3.candidate_gate(lead(), [], NOW,72), "candidate")
    def test_repeated_employer_is_cooldown(self):
        self.assertEqual(v3.candidate_gate(lead(company="Stripe"), [], NOW,72), "repeat_employer_cooldown")
        self.assertEqual(v3.candidate_gate(lead(company="Datadog"), [], NOW,72), "repeat_employer_cooldown")
    def test_existing_application(self):
        rows=[{"company":"Fresh Employer","title":"Strategic Partnerships Manager","url":"","date":""}]
        self.assertEqual(v3.candidate_gate(lead(),rows,NOW,72),"already_applied")
    def test_prior_company_not_blocked_for_new_role(self):
        rows=[{"company":"Fresh Employer","title":"Category Manager","url":"","date":""}]
        self.assertEqual(v3.candidate_gate(lead(),rows,NOW,72),"candidate")
    def test_technical_role_excluded(self):
        self.assertEqual(v3.candidate_gate(lead(title="Senior Partner Solutions Manager, Strategic Partnerships"),[],NOW,72),"title_not_commercial")
    def test_old_first_seen_not_new(self):
        j=lead()
        j["first_seen"]="2026-01-01T00:00:00Z"
        self.assertEqual(v3.candidate_gate(j,[],NOW,72),"not_recent_to_feed")
    def test_non_us_remote_is_not_us(self):
        j=lead()
        j["location"]="Remote, Canada"
        j["remote"]=True
        self.assertEqual(v3.candidate_gate(j,[],NOW,72),"location_unverified")
    def test_employer_verification_urls(self):
        self.assertEqual(v3.verified_url(lead())[0],"greenhouse")
        j=lead(ats="Lever",url="https://jobs.lever.co/company/abcdef")
        self.assertEqual(v3.verified_url(j)[1],"https://api.lever.co/v0/postings/company/abcdef")
        j=lead(ats="Workday",url="https://fis.wd5.myworkdayjobs.com/en-US/SearchJobs/job/Atlanta/Account_Manager_JR0308993")
        self.assertIn("/wday/cxs/fis/SearchJobs/job/Atlanta/",v3.verified_url(j)[1])
    def test_unsupported_link_is_not_accepted(self):
        self.assertIsNone(v3.verified_url(lead(url="https://example.net/jobs/123")))
    def test_post_age_actual_not_first_seen(self):
        self.assertEqual(v3.age_days("Posted 30+ Days Ago",NOW),30)
        self.assertEqual(v3.age_days("Posted 2 Weeks Ago",NOW),14)
        self.assertIsNone(v3.age_days(None,NOW))
    def test_recent_greenhouse_is_verified(self):
        s=Mock()
        s.get.return_value=response(greenhouse())
        j,reason=v3.verify(lead(),now=NOW,session=s)
        self.assertEqual(reason,"verified")
        self.assertTrue(j["employer_verified"])
        self.assertEqual(j["fit_tier"],"Strong")
    def test_old_published_greenhouse_is_excluded_even_when_first_seen_today(self):
        s=Mock()
        s.get.return_value=response(greenhouse(when="2026-10-01T00:00:00Z"))
        j,reason=v3.verify(lead(),now=NOW,session=s)
        self.assertIsNone(j)
        self.assertEqual(reason,"posted_too_old")
    def test_unknown_published_date_not_promoted(self):
        s=Mock()
        s.get.return_value=response(greenhouse(when=None))
        j,reason=v3.verify(lead(),now=NOW,session=s)
        self.assertEqual(reason,"posting_date_unverified")
    def test_closed_employer_listing_not_promoted(self):
        s=Mock()
        s.get.return_value=response({},404)
        j,reason=v3.verify(lead(),now=NOW,session=s)
        self.assertEqual(reason,"closed")
    def test_workday_old_fis_rejected(self):
        j=lead(title="Account Manager Sr Lead, Strategic Accounts",company="FIS",ats="Workday",
               url="https://fis.wd5.myworkdayjobs.com/en-US/SearchJobs/job/US-GA-ATL-201-STE-900/Account-Manager-Sr-Lead--Strategic-Accounts_JR0308993")
        response_json={"canApply":True,"jobPostingInfo":{"title":j["title"],
                   "location":"Atlanta, GA","postedOn":"Posted 30+ Days Ago",
                   "jobDescription":"Manage enterprise accounts, commercial negotiations, sales targets and client growth to improve partner account retention."}}
        s=Mock()
        s.get.return_value=response(response_json)
        valid,reason=v3.verify(j,now=NOW,session=s)
        self.assertIsNone(valid)
        self.assertEqual(reason,"posted_too_old")
    def test_technical_mandatory_requirements_screen(self):
        j=lead()
        data=greenhouse()
        data["content"]="Hands-on experience with AWS architecture and implementation in enterprise production environments. Must have experience with Kubernetes, CI/CD, DevSecOps, and solution architecture. Partner with commercial executives and enterprise stakeholders."
        s=Mock()
        s.get.return_value=response(data)
        _,reason=v3.verify(j,now=NOW,session=s)
        self.assertEqual(reason,"mandatory_technical_fit")
    def test_fifteen_company_cap_and_audit_render(self):
        jobs=[]
        for i in range(18):
            j=lead(company="Company "+str(i))
            j.update(fit_tier="Strong",score=70,posted_age_days=2.0,fit_reason="Relevant commercial work",gap_reason="Review qualifications")
            jobs.append(j)
        with patch.object(v3,"verify",side_effect=[(j,"verified") for j in jobs]):
            kept,counts=v3.verify_batch(jobs,NOW,15)
        self.assertEqual(len(kept),15)
        self.assertEqual(counts["shortlisted"],15)
        html=v3.build_report({"generated_at":NOW.isoformat(),"jobs":kept,"counts":dict(counts)})
        self.assertIn("Verified commercial jobs",html)
        self.assertNotIn("<script>",html)
    def test_manifest_validation(self):
        s=Mock()
        s.get.return_value=response({"chunks":["jobs_chunk_0.json.gz"],"totalJobs":100})
        self.assertEqual(len(v3.fetch_manifest(v3.MANIFEST_URL,s)["chunks"]),1)
        s.get.return_value=response({"chunks":["../evil.py"]})
        with self.assertRaises(ValueError):
            v3.fetch_manifest(v3.MANIFEST_URL,s)

if __name__=="__main__":
    unittest.main()
