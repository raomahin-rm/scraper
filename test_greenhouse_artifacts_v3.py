import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.exceptions import InvalidTag
import greenhouse_artifacts_v3 as a

class ArtifactTests(unittest.TestCase):
    def test_private_roundtrip_and_tamper_protection(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'APPLICATION_PACKET_KEY':base64.b64encode(os.urandom(32)).decode()}):
            p=Path(d);(p/'source').mkdir();(p/'source'/'packet.json').write_text('{"email":"private@example.com"}');(p/'source'/'filled.png').write_bytes(b'private screenshot')
            a.pack(p/'source',p/'packets.enc')
            self.assertNotIn(b'private@example.com',(p/'packets.enc').read_bytes())
            a.unpack(p/'packets.enc',p/'restored');self.assertEqual((p/'restored'/'packet.json').read_text(),(p/'source'/'packet.json').read_text())
            self.assertFalse((p/'restored'/'filled.png').exists())
            b=bytearray((p/'packets.enc').read_bytes());b[-1]^=1;(p/'packets.enc').write_bytes(b)
            with self.assertRaises(InvalidTag):a.unpack(p/'packets.enc',p/'tampered')
