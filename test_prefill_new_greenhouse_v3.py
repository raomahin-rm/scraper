import unittest
from prefill_new_greenhouse_v3 import select
class V3GreenhouseWorklistTests(unittest.TestCase):
    def test_only_new_greenhouse_drafts_and_approved_data_unchanged(self):
        db={"version":1,"applications":{
            "a":{"status":"draft","url":"https://job-boards.greenhouse.io/example/jobs/123"},
            "b":{"status":"ready_for_review","url":"https://job-boards.greenhouse.io/example/jobs/456"},
            "c":{"status":"draft","url":"https://jobs.ashbyhq.com/acme/abc"},
            "d":{"status":"draft","url":"https://job-boards.greenhouse.io/test/jobs/789"},
        }}
        summary={"new_applications":[{"id":i} for i in ["a","b","c","d"]]}
        drafts={"drafts":[{"id":i,"why_company_draft":"Test"} for i in db["applications"]]}
        q,filtered,ids=select(db,summary,drafts,6)
        self.assertEqual(ids,["a","d"])
        self.assertEqual(len(q["applications"]),2)
        self.assertEqual(len(filtered["drafts"]),2)
        self.assertEqual(db["applications"]["b"]["status"],"ready_for_review")
    def test_selection_limit(self):
        db={"version":1,"applications":{str(i):{"status":"draft","url":f"https://job-boards.greenhouse.io/example/jobs/{i}"} for i in range(1,10)}}
        summary={"new_applications":[{"id":str(i)} for i in range(1,10)]}
        drafts={"drafts":[{"id":str(i)} for i in range(1,10)]}
        _,_,ids=select(db,summary,drafts,3)
        self.assertEqual(len(ids),3)

if __name__=="__main__":
    unittest.main()
