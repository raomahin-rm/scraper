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
    def test_live_real_field_labels(self):
        self.assertIn("Chicago",self.answer("Due to current team needs, we are only considering candidates based in the USA. Please confirm you're based in the USA."))
        self.assertIn("Central",self.answer("What is the Time Zone you most commonly operate in?"))
        self.assertEqual(self.answer("How did you hear about Mixpanel as an Employer?"),"Online job posting.")
        self.assertEqual(self.answer("How soon would you be available to start?"),"Three weeks")
    def test_current_employment_from_profile(self):
        profile={"verified_experience":[{"employer":"University of Chicago Booth School of Business","role":"Custom Program Learning Specialist","period":"October 2026 - Present"}]}
        self.assertIn("University of Chicago",fact_answer("Current Employer",APP,{},profile))
        self.assertEqual(fact_answer("Current Job Title",APP,{},profile),"Custom Program Learning Specialist")
    def test_confirmed_private_user_answers(self):
        policy={"prior_employment_at_named_employers":"none",
                "restrictive_agreements":"none",
                "salary_preference":"advertised_range_midpoint",
                "voluntary_demographics":"individual_review",
                "recruiter_sms":"yes",
                "privacy_and_recording":"individual_review",
                "specialized_experience":"none"}
        profile=dict(PROFILE,_confirmed=policy)
        self.assertEqual(fact_answer("Have you worked at DoorDash?",dict(APP,company="doordashusa"),{},profile),"No")
        self.assertEqual(fact_answer("Have you ever been employed by Mozilla before?",dict(APP,company="mozilla"),{},profile),"No")
        self.assertEqual(fact_answer("Are you subject to any non-compete or non-solicitation agreements?",APP,{},profile),"No")
        self.assertEqual(fact_answer("Would you like to receive communications via SMS and/or WhatsApp?",APP,{},profile),"Yes")
        self.assertEqual(fact_answer("Do you have experience working with Fortune 500 customers?",APP,{},profile),"No")
        self.assertEqual(fact_answer("What salary range are you looking for?",APP,{"content":""},profile),"$90,000")
        self.assertEqual(fact_answer("What is your expected salary range?",APP,{"content":"Base salary range: $116,900 - $137,500 annually."},profile),"$127,200")
        for consent in ("Applicant Privacy Acknowledgement", "Please acknowledge the Interview Recording Policy",
                        "Your gender", "I identify my ethnicity as"):
            self.assertIsNone(fact_answer(consent,APP,{},profile))
    def test_unconfirmed_company_history_is_not_inferred(self):
        p=dict(PROFILE,_confirmed={"prior_employment_at_named_employers":"none"})
        self.assertIsNone(fact_answer("Have you ever been employed by Acme before?",dict(APP,company="acme"),{},p))
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
