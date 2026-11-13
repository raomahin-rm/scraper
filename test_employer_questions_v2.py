import unittest
from employer_questions_v2 import greenhouse_parts,extract_questions,inspect

class FakeResponse:
    def raise_for_status(self): pass
    def json(self): return {"questions":[{"label":"Do you need sponsorship?","required":True,"fields":[{"name":"question_1","type":"input_text"}]}]}
class FakeSession:
    def get(self,url,timeout):
        assert url=="https://boards-api.greenhouse.io/v1/boards/example/jobs/123?questions=true"
        return FakeResponse()
class EmployerQuestionTests(unittest.TestCase):
    def test_greenhouse_url(self):
        self.assertEqual(greenhouse_parts("https://job-boards.greenhouse.io/example/jobs/123"),("example","123"))
    def test_reject_non_greenhouse(self):
        self.assertIsNone(greenhouse_parts("https://example.com/example/jobs/123"))
    def test_reject_non_https(self):
        self.assertIsNone(greenhouse_parts("http://boards.greenhouse.io/example/jobs/123"))
    def test_extract_required_questions(self):
        q=extract_questions(FakeResponse().json())
        self.assertTrue(q[0]["required"])
        self.assertEqual(q[0]["label"],"Do you need sponsorship?")
    def test_inspect_does_not_submit(self):
        x=inspect({"id":"1","company":"Example","title":"Manager","application_url":"https://job-boards.greenhouse.io/example/jobs/123"},FakeSession())
        self.assertEqual(x["status"],"questions_retrieved")
        self.assertFalse(x["submitted"])
    def test_unsupported_requires_review(self):
        x=inspect({"id":"1","company":"Example","title":"Manager","application_url":"https://example.com/job"})
        self.assertEqual(x["status"],"manual_review_required")
if __name__=="__main__":unittest.main()
