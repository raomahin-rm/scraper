"""Offline regression tests for replacement scraper v2."""
import unittest
from unittest.mock import Mock
import scraper_v2 as v2

class ReplacementTests(unittest.TestCase):
    def test_canonical_tracking(self):
        self.assertEqual(v2.canonical("https://EXAMPLE.com/job/123/?utm_source=mail&ref=x#apply"),"https://example.com/job/123")
    def test_ats_endpoints(self):
        self.assertIn("/boards/stripe/jobs",v2.endpoint({"ats":"greenhouse","slug":"stripe"}))
        self.assertIsNone(v2.endpoint({"ats":"manual","slug":""}))
    def test_extract_greenhouse(self):
        row={"ats":"greenhouse","slug":"stripe","name":"Stripe"}
        data={"jobs":[{"id":42,"title":"Partnerships Manager","location":{"name":"Chicago, IL"},"absolute_url":"https://example.com/job/42?utm_source=email"}]}
        jobs=list(v2.extract(row,data))
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["id"],"greenhouse:stripe:42")
        self.assertEqual(jobs[0]["location"],"Chicago, IL")
    def test_extract_ashby(self):
        row={"ats":"ashby","slug":"openai","name":"OpenAI"}
        data={"jobs":[{"id":"a1","title":"Account Manager","location":"New York","jobUrl":"https://example.com/a1"}]}
        self.assertEqual(list(v2.extract(row,data))[0]["id"],"ashby:openai:a1")
    def test_duplicate_id_dedup(self):
        row={"ats":"greenhouse","slug":"stripe","name":"Stripe"}
        payload={"jobs":[{"id":1,"title":"Partnerships Manager","location":{"name":"Chicago"},"absolute_url":"https://example.com/1"}]}
        session=Mock()
        response=Mock()
        response.json.return_value=payload
        response.raise_for_status.return_value=None
        session.get.return_value=response
        jobs,failures=v2.scan([row,row],session,delay=0)
        self.assertEqual(len(jobs),1)
        self.assertEqual(failures,[])
    def test_workday_pagination_collects_all_pages(self):
        row={"ats":"workday","tenant":"example","board":"External","subdomain":"wd5","name":"Example"}
        def page(start, count):
            return {"total":5,"jobPostings":[{"externalPath":"/job/"+str(i),"title":"Partnerships Manager","locationsText":"Chicago, IL"} for i in range(start,start+count)]}
        session=Mock()
        responses=[]
        for payload in (page(0,2),page(2,2),page(4,1)):
            response=Mock()
            response.json.return_value=payload
            responses.append(response)
        session.post.side_effect=responses
        jobs,failures=v2.scan([row],session,delay=0,workday_page_size=2)
        self.assertEqual(len(jobs),5)
        self.assertEqual(failures,[])
        self.assertEqual([call.kwargs["json"]["offset"] for call in session.post.call_args_list],[0,2,4])
    def test_workday_repeated_page_stops(self):
        row={"ats":"workday","tenant":"example","board":"External","subdomain":"wd5","name":"Example"}
        session=Mock()
        session.post.return_value.json.return_value={"total":100,"jobPostings":[{"externalPath":"/job/1","title":"Partnerships Manager","locationsText":"Chicago, IL"}]}
        jobs,failures=v2.scan([row],session,delay=0,workday_page_size=1)
        self.assertEqual(len(jobs),1)
        self.assertEqual(len(failures),1)
        self.assertIn("repeated page",failures[0]["reason"])
    def test_invalid_payload_records_failure(self):
        row={"ats":"greenhouse","slug":"stripe","name":"Stripe"}
        session=Mock()
        response=Mock()
        response.json.return_value={"jobs":"not-a-list"}
        session.get.return_value=response
        jobs,failures=v2.scan([row],session,delay=0)
        self.assertEqual(jobs,[])
        self.assertEqual(len(failures),1)

if __name__=="__main__":
    unittest.main()
