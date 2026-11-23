import unittest
from verified_form_facts_v3 import fact_answer

PROFILE={"verified_experience":[{"employer":"Leverify LLC","evidence":"US supplier relationships; $84K cost savings; $700K supplier credit facility"}]}
APP={"title":"Enterprise Account Manager","company":"Acme"}
class VerifiedFormFactsTests(unittest.TestCase):
    def answer(self,q):
        return fact_answer(q,APP,{},PROFILE)
    def test_location(self):
        self.assertIn("Chicago",self.answer("Please confirm you're based in the USA."))
    def test_timezone(self):
        self.assertIn("Central",self.answer("What is the Time Zone you most commonly operate in?"))
    def test_verified_motivation(self):
        a=self.answer("In 2-3 sentences, what excites you about this position?")
        self.assertIn("Leverify",a)
        self.assertIn("$700K",a)
    def test_linkedin(self):
        self.assertTrue(self.answer("LinkedIn Profile").startswith("https://www.linkedin.com/"))
    def test_never_infer_consent_or_sponsorship(self):
        for q in ["Applicant Privacy Acknowledgement",
                  "Do you require sponsorship now or in the future?",
                  "Are you subject to any non-compete agreement?",
                  "Please consent to interview recording",
                  "What is your gender?",
                  "What is your sexual orientation?",
                  "Have you worked for DoorDash?"]:
            with self.subTest(question=q):
                self.assertIsNone(self.answer(q))
if __name__=="__main__":
    unittest.main()
