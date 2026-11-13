import unittest
from application_queue_v2 import import_jobs, set_materials, transition, identity

def job(url="https://example.com/jobs/123?utm_source=x"):
    return {"company":"Example","title":"Partnerships Manager","location":"Chicago","url":url,"id":"123"}

class ApplicationQueueTests(unittest.TestCase):
    def setUp(self):
        self.db={"version":1,"applications":{}}
        import_jobs(self.db,[job()])
        self.uid=identity(job())
    def test_duplicate_url_with_tracking_is_not_reimported(self):
        self.assertEqual(import_jobs(self.db,[job("https://example.com/jobs/123?utm_medium=email")]),0)
        self.assertEqual(len(self.db["applications"]),1)
    def test_cannot_approve_draft(self):
        with self.assertRaises(ValueError): transition(self.db,self.uid,"approved")
    def test_requires_review_and_approval(self):
        set_materials(self.db,self.uid,"resume.pdf",{"work_authorization":"Needs review"})
        transition(self.db,self.uid,"approved")
        self.assertEqual(self.db["applications"][self.uid]["status"],"approved")
    def test_cannot_claim_submission_without_confirmation(self):
        set_materials(self.db,self.uid,"resume.pdf",{})
        transition(self.db,self.uid,"approved")
        with self.assertRaises(ValueError): transition(self.db,self.uid,"submitted")
    def test_records_confirmed_submission(self):
        set_materials(self.db,self.uid,"resume.pdf",{})
        transition(self.db,self.uid,"approved")
        transition(self.db,self.uid,"submitted",confirmation="employer-confirmation-123")
        self.assertEqual(self.db["applications"][self.uid]["confirmation"],"employer-confirmation-123")
    def test_cannot_submit_twice(self):
        set_materials(self.db,self.uid,"resume.pdf",{})
        transition(self.db,self.uid,"approved")
        transition(self.db,self.uid,"submitted",confirmation="123")
        with self.assertRaises(ValueError): transition(self.db,self.uid,"submitted",confirmation="124")
if __name__=="__main__":
    unittest.main()
