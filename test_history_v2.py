import tempfile
import unittest
from pathlib import Path
from history_v2 import load_history,new_jobs,mark_delivered,save_history

class HistoryTests(unittest.TestCase):
    def test_distinct_requisitions(self):
        a={"id":"gh:1","title":"Partner Manager"}
        b={"id":"gh:2","title":"Partner Manager"}
        hist=mark_delivered([a],{},delivered_at="2026-01-01")
        self.assertEqual(new_jobs([a,b],hist),[b])
    def test_preview_does_not_mutate_history(self):
        hist={"gh:1":{"delivered_at":"old"}}
        new_jobs([{"id":"gh:2"}],hist)
        self.assertEqual(len(hist),1)
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"history.json"
            self.assertEqual(load_history(path),{})
            hist=mark_delivered([{"id":"gh:1","company":"A"}],{})
            save_history(path,hist)
            self.assertEqual(load_history(path),hist)
    def test_no_pruning(self):
        hist={"old":{"delivered_at":"2020-01-01"}}
        self.assertIn("old",mark_delivered([{"id":"new"}],hist))
if __name__=="__main__":
    unittest.main()
