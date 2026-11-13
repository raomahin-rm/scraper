import unittest
from application_answers_v2 import classify,draft,draft_all
class AnswersTests(unittest.TestCase):
    def test_sponsorship_precedence(self):
        self.assertEqual(classify("Are you authorized to work and will you require visa sponsorship?"),"sponsorship")
    def test_authorization(self):
        self.assertEqual(classify("Are you legally authorized to work in the United States?"),"work_authorization")
    def test_no_guess(self):
        self.assertIsNone(draft("Expected salary?",{})["suggested_answer"])
    def test_unapproved_answer_hidden(self):
        self.assertIsNone(draft("Are you willing to relocate?",{"relocation":{"answer":"Yes","approved":False}})["suggested_answer"])
    def test_approved_answer_still_reviewed(self):
        result=draft("Are you willing to relocate?",{"relocation":{"answer":"Yes","approved":True}})
        self.assertEqual(result["suggested_answer"],"Yes")
        self.assertTrue(result["requires_review"])
    def test_unrecognized_question(self):
        self.assertIsNone(draft_all(["Describe a difficult negotiation"],{})[0]["category"])
if __name__=="__main__": unittest.main()
