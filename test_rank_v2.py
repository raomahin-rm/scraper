import unittest
from rank_v2 import evaluate, shortlist, location_class

def job(title, location="Chicago, IL", company="Example", uid="1"):
    return {"id":uid,"title":title,"location":location,"company":company,"url":"https://example.com/"+uid,"source":"greenhouse"}

class RankingTests(unittest.TestCase):
    def test_strategic_partnerships(self):
        result, status = evaluate(job("Senior Strategic Partnerships Manager"))
        self.assertEqual(status,"accepted")
        self.assertEqual(result["location_status"],"us")
    def test_account_management(self):
        self.assertIsNotNone(evaluate(job("Enterprise Account Manager"))[0])
    def test_assistant_partnerships_manager(self):
        self.assertEqual(evaluate(job("Assistant Partnerships Manager"))[1],"accepted")
    def test_associate_account_manager(self):
        self.assertEqual(evaluate(job("Associate Account Manager"))[1],"accepted")
    def test_technical_account_without_evidence(self):
        self.assertEqual(evaluate(job("Technical Account Manager"))[1],"technical_fit_unverified")
    def test_technical_account_with_commercial_evidence(self):
        j=job("Technical Account Manager")
        j["description"]="Manage enterprise renewals and commercial expansion."
        self.assertEqual(evaluate(j)[1],"accepted")
    def test_reject_engineering_management(self):
        self.assertEqual(evaluate(job("Engineering Manager, Partnerships"))[1],"blocked_title")
    def test_reject_inside_sales(self):
        self.assertEqual(evaluate(job("Inside Sales Manager"))[1],"blocked_title")
    def test_reject_engineering(self):
        self.assertEqual(evaluate(job("Partnerships Engineer"))[1],"blocked_title")
    def test_non_us(self):
        self.assertEqual(evaluate(job("Partnerships Manager","London, United Kingdom"))[1],"non_us")
    def test_ambiguous_location_separate(self):
        result=shortlist([job("Partnerships Manager","Remote")])
        self.assertEqual(len(result["top"]),0)
        self.assertEqual(len(result["review_location"]),1)
    def test_max_two_jobs_per_company(self):
        jobs = [job("Senior Strategic Partnerships Manager " + str(i), company="A", uid=str(i)) for i in range(6)]
        jobs += [job("Senior Strategic Partnerships Manager " + str(i), company="B", uid="b"+str(i)) for i in range(4)]
        result = shortlist(jobs, limit=10)
        self.assertEqual(len(result["top"]), 4)
        self.assertEqual(sum(j["company"] == "A" for j in result["top"]), 2)
        self.assertEqual(sum(j["company"] == "B" for j in result["top"]), 2)
        self.assertEqual(result["total_us_matches"], 10)
    def test_same_role_across_requisitions_suppressed(self):
        result=shortlist([job("Partnerships Manager",uid="1"),job("Partnerships Manager",uid="2")])
        self.assertEqual(result["total_us_matches"],1)
        self.assertEqual(result["counts"]["same_role_different_posting"],1)
    def test_different_specializations_preserved(self):
        result=shortlist([job("Senior Partnerships Manager, Payments",uid="1"),job("Senior Partnerships Manager, Grocery",uid="2")])
        self.assertEqual(result["total_us_matches"],2)
    def test_same_id_dedup(self):
        result=shortlist([job("Partnerships Manager"),job("Partnerships Manager")])
        self.assertEqual(result["total_us_matches"],1)
    def test_preferred_city(self):
        a=evaluate(job("Partnerships Manager","Chicago, IL"))[0]
        b=evaluate(job("Partnerships Manager","Miami, FL"))[0]
        self.assertGreater(a["score"],b["score"])
    def test_foreign_only(self):
        self.assertEqual(location_class("Toronto, Canada"),"non_us")

if __name__=="__main__":
    unittest.main()
