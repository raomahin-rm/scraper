import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deliver_v2 import deliver, prepare

class DeliveryTests(unittest.TestCase):
    def test_filters_seen_and_renders_only_new(self):
        pending, html = prepare({"top":[{"id":"1","title":"Old"},{"id":"2","title":"New","company":"A","url":"https://example.com"}]}, {"1":{"delivered_at":"yesterday"}})
        self.assertEqual([j["id"] for j in pending],["2"])
        self.assertIn("New",html)
        self.assertNotIn(">Old<",html)
    def test_dry_run_does_not_change_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/"jobs.json"
            source.write_text(json.dumps({"top":[{"id":"new","title":"Partner Manager","url":"https://example.com"}]}))
            history=root/"history.json"
            with patch.dict("os.environ",{},clear=True):
                self.assertEqual(deliver(source,history,root/"preview.html",send=False),1)
            self.assertFalse(history.exists())
            self.assertTrue((root/"preview.html").exists())
    def test_empty_send_does_not_need_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/"jobs.json"
            source.write_text(json.dumps({"top":[]}))
            with patch.dict("os.environ",{},clear=True):
                self.assertEqual(deliver(source,root/"history.json",root/"preview.html",send=True),0)
if __name__=="__main__":
    unittest.main()
