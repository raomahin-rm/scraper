import unittest
from employer_answer_matches_v2 import match_application

class AnswerMatchTests(unittest.TestCase):
    def setUp(self):
        self.record={"id":"a","company":"Example","title":"Manager","application_url":"https://example.com/jobs/1","status":"questions_retrieved","questions":[]}
        self.bank={"sponsorship":{"answer":"Yes","approved":True},"salary":{"answer":"$80,000–$100,000; negotiable","approved":True}}
    def test_approved_sponsorship(self):
        self.record["questions"]=[{"label":"Will you require visa sponsorship?","required":True}]
        r=match_application(self.record,self.bank)
        self.assertEqual(r["question_matches"][0]["suggested_answer"],"Yes")
        self.assertFalse(r["submission_approved"])
    def test_gender_never_inferred(self):
        self.record["questions"]=[{"label":"What is your gender?","required":False}]
        r=match_application(self.record,self.bank)
        self.assertIsNone(r["question_matches"][0]["suggested_answer"])
        self.assertEqual(r["question_matches"][0]["category"],"voluntary_demographic")
    def test_disability_never_inferred(self):
        self.record["questions"]=[{"label":"Do you have a disability?","required":False}]
        self.assertIsNone(match_application(self.record,self.bank)["question_matches"][0]["suggested_answer"])
    def test_unknown_needs_review(self):
        self.record["questions"]=[{"label":"Why this company?","required":True}]
        self.assertIsNone(match_application(self.record,self.bank)["question_matches"][0]["suggested_answer"])
    def test_never_submitted(self):
        self.assertFalse(match_application(self.record,self.bank)["submitted"])
if __name__=="__main__":unittest.main()
