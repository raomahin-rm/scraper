"""Phase 1 regression checks; never send email or modify production state."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import job_scraper as js

def job(uid, source="greenhouse", url="https://jobs.example.com/abc?utm_source=email"):
    return js.Job(source, uid, "Example", "Partnerships Manager", "Chicago, IL", url,
                  datetime.now(timezone.utc), "Partnerships channel management")

assert js.canonical_url("https://www.Example.com/en-US/jobs/abc/?utm_source=mail") == "example.com/jobs/abc"
assert js.location_info("Remote")[0] == "remote"
a = job("gh:abc:123")
b = job("gh:abc:123", url="https://jobs.example.com/abc?utm_source=other")
assert js.job_identities(a) & js.job_identities(b)
assert js.job_identities(a) & js.job_identities(job("lv:abc:456", "lever", "https://jobs.example.com/abc"))
assert not (js.job_identities(a) & js.job_identities(job("gh:abc:999", url="https://jobs.example.com/xyz")))
with TemporaryDirectory() as d:
    p = Path(d) / "seen.json"
    with patch.object(js, "SEEN_FILE", p):
        js.save_seen({"old-job": "2025-01-01T00:00:00+00:00"})
        assert "old-job" in js.load_seen()
print("Phase 1 regression tests passed")
