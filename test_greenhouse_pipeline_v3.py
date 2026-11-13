import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import greenhouse_pipeline_v3 as g


def fixtures():
    app = {"id":"abc", "company":"Example", "title":"Enterprise Account Manager", "url":"https://job-boards.greenhouse.io/example/jobs/123", "location":"Chicago, IL", "status":"draft", "events":[]}
    job = {"id":123, "title":app['title'], "location":{"name":"Chicago, IL"}, "content":"<p>Own enterprise account growth. Experience negotiating contracts required.</p>", "questions":[
        {"label":"First Name", "required":True, "fields":[{"name":"first_name", "type":"input_text", "values":[]}]},
        {"label":"Are you legally authorized to work in the United States?", "required":True,"fields":[{"name":"q1", "type":"multi_value_single_select", "values":[{"label":"Yes", "value":1},{"label":"No", "value":0}]}]},
        {"label":"Will you require sponsorship in the future?", "required":True,"fields":[{"name":"q2", "type":"multi_value_single_select", "values":[{"label":"Yes", "value":1}]}]}]}
    bank = {"work_authorization":{"approved":True,"answer":"Yes"}, "sponsorship":{"approved":True,"answer":"Yes"}}
    packet = g.prepare(app,job,bank,{}, {"verified_experience":[]}, {"first_name":"Rao"})
    packet['live_schema']=[{'id':'first_name','type':'text','required':True,'label':'First Name'}]
    return app, job, bank, packet


def comment(packet):
    return {"id":1, "user":{"login":g.OWNER}, "body":f"I APPROVE SUBMIT {packet['id']} {g.approval_digest(packet)}", "created_at":g.now()}

class PipelineTests(unittest.TestCase):
    def test_only_direct_greenhouse_is_supported(self):
        for url in ['https://evil.example/x','https://job-boards.greenhouse.io.evil.com/example/jobs/123','http://job-boards.greenhouse.io/example/jobs/123']:
            with self.assertRaises(ValueError):g.fetch_job(url)
    def test_closed_job_and_mismatch(self):
        _,job,_,_=fixtures();job['id']=124
        session=Mock();session.get.return_value.json.return_value=job
        with self.assertRaises(ValueError):g.fetch_job('https://job-boards.greenhouse.io/example/jobs/123',session)
    def test_screen_description_restriction(self):
        app,job,_,_=fixtures();job['content']='We cannot sponsor visas for this position.'
        self.assertEqual(g.screen(app,job)['decision'],'blocked')
    def test_unknown_and_demographics_are_unanswered(self):
        _,_,bank,_=fixtures()
        for label in ['Gender','Have you worked at DoorDash?','Applicant Privacy Acknowledgement','Will you now require immigration sponsorship?','Are you authorized to work in Canada?','Are you authorized to work without restriction in the United States?','Do you have 10 years of experience?']:
            self.assertIsNone(g.suggested({'label':label},bank)[0],label)
    def test_public_status_never_contains_private_answer_values(self):
        _,_,_,packet=fixtures();packet['answers'][0]['value']='private@example.com'
        packet['documents']={'resume':{'path':'/private/person.pdf','sha256':'hash'}}
        result={'filled_fields':['first_name'],'errors':[],'submitted':False}
        summary=json.dumps(g.public_summary(packet,result))
        self.assertNotIn('private@example.com',summary)
        self.assertNotIn('/private/person.pdf',summary)
        self.assertIn('packet_digest',summary)
    def test_options_are_exact(self):
        app,job,bank,_=fixtures(); job['questions'][1]['fields'][0]['values']=[{'label':'Yes, permanently','value':1}]
        p=g.prepare(app,job,bank,{}, {},{'first_name':'Rao'})
        self.assertIn(job['questions'][1]['label'],p['missing_required'])
    def test_requires_owner_explicit_individual_approval(self):
        _,_,_,p=fixtures()
        for c in [{},dict(comment(p),user={'login':'codex'}),dict(comment(p),body='Approve all'),dict(comment(p),body='I APPROVE SUBMIT other '+g.approval_digest(p))]:
            with self.assertRaises(ValueError):g.validate_approval(p,c)
        self.assertEqual(g.validate_approval(p,comment(p))['actor'],g.OWNER)
    def test_material_changes_invalidate_approval(self):
        _,_,_,p=fixtures();c=comment(p)
        for key,value in [('url','https://job-boards.greenhouse.io/example/jobs/124'),('job_fingerprint','changed'),('live_schema',[{'id':'new'}])]:
            q=copy.deepcopy(p);q[key]=value
            with self.assertRaises(ValueError):g.validate_approval(q,c)
        q=copy.deepcopy(p);q['answers'][0]['value']='Someone else'
        with self.assertRaises(ValueError):g.validate_approval(q,c)
    def test_missing_live_review_blocks_approval(self):
        _,_,_,p=fixtures();p.pop('live_schema')
        with self.assertRaises(ValueError):g.validate_approval(p,comment(p))
    def test_missing_fields_blocks_approval(self):
        _,_,_,p=fixtures();p['missing_required']=['consent']
        with self.assertRaises(ValueError):g.validate_approval(p,comment(p))
    def test_approval_expires(self):
        _,_,_,p=fixtures();c=comment(p);c['created_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):g.validate_approval(p,c)
    def test_changed_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'resume.pdf';path.write_bytes(b'original')
            _,_,_,p=fixtures();p['documents']={'resume':{'path':str(path),'sha256':g.file_hash(path)}}
            c=comment(p);path.write_bytes(b'changed')
            with self.assertRaises(ValueError):g.assert_documents(p)
            p['documents']['resume']['sha256']=g.file_hash(path)
            with self.assertRaises(ValueError):g.validate_approval(p,c)
    def test_duplicate_and_uncertain_attempts_never_retry(self):
        app,_,_,p=fixtures()
        for status in ['submission_started','submission_unknown','submitted']:
            q=copy.deepcopy(app);q['events']=[{'status':status}];q['id']='alias'
            with self.assertRaises(ValueError):g.check_duplicate({'applications':{'alias':q}},p)
    def test_preview_network_guard(self):
        for method in ['POST','PUT','PATCH','DELETE']:
            self.assertFalse(g.allow_preview_request(method,'https://boards-api.greenhouse.io/v1/boards/example/jobs/123',{}))
        self.assertTrue(g.allow_preview_request('GET','https://boards-api.greenhouse.io/v1/boards/example/jobs/123',{}))
    def test_error_is_persisted_without_contact_values(self):
        app,_,_,p=fixtures()
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'db.json';g.save(db,{'applications':{'abc':app}})
            with patch.object(g,'fetch_job',side_effect=RuntimeError('private@example.com')):
                with self.assertRaises(RuntimeError):g.execute(p,db,Path(d)/'out')
            record=json.loads(db.read_text());self.assertEqual(record['applications']['abc']['pipeline_status'],'error')
            self.assertNotIn('private@example.com',db.read_text())

if __name__=='__main__':unittest.main()

class DurableJournalTests(unittest.TestCase):
    def test_missing_token_blocks_submission(self):
        _,_,_,p=fixtures()
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):g.durable_attempt(p,{'packet_digest':'x','comment_id':1})
    def test_prior_reservation_blocks_retry(self):
        _,_,_,p=fixtures();session=Mock();session.get.return_value.status_code=200
        with patch.dict('os.environ',{'GH_TOKEN':'test-only'}):
            with self.assertRaises(ValueError):g.durable_attempt(p,{'packet_digest':'x','comment_id':1},session=session)
        session.put.assert_not_called()
    def test_reservation_written_before_attempt(self):
        _,_,_,p=fixtures();session=Mock();absent=Mock();absent.status_code=404;branch=Mock();branch.status_code=200
        session.get.side_effect=[absent,branch]
        with patch.dict('os.environ',{'GH_TOKEN':'test-only'}):g.durable_attempt(p,{'packet_digest':'x','comment_id':1},session=session)
        body=session.put.call_args.kwargs['json'];self.assertNotIn('sha',body)
        import base64
        payload=json.loads(base64.b64decode(body['content']));self.assertEqual(payload['state'],'submission_started')
        self.assertNotIn('answers',payload)
