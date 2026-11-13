import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch, Mock
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from greenhouse_private_v3 import make_keyring, private_key, seal, open_bundle, derive, bootstrap

class PrivateMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secret='test-only-high-entropy-existing-secret';cls.ring=make_keyring(cls.secret)
    def test_roundtrip_and_no_plaintext(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'source').mkdir();(p/'source'/'contact.json').write_text('{"email":"private@example.com"}')
            (p/'source'/'overrides.json').write_text('{}');(p/'source'/'resume.pdf').write_bytes(b'%PDF-fixture')
            (p/'source'/'ignored.txt').write_text('do not include')
            bundle=seal(self.ring,p/'source');self.assertNotIn('private@example.com',json.dumps(bundle))
            self.assertNotIn(self.secret,json.dumps(self.ring))
            public_only={k:v for k,v in self.ring.items() if k!='encrypted_private_pem'}
            self.assertIsInstance(seal(public_only,p/'source'),dict)
            names=open_bundle(self.ring,bundle,self.secret,p/'out')
            self.assertEqual(set(names),{'contact.json','overrides.json','resume.pdf'})
            self.assertEqual((p/'out'/'contact.json').read_text(),(p/'source'/'contact.json').read_text())
    def test_wrong_secret_never_replaces_key(self):
        with self.assertRaises(ValueError):private_key(self.ring,'wrong-secret-long-enough')
    def test_key_fingerprint_tampering_rejected(self):
        ring=copy.deepcopy(self.ring);ring['key_id']='changed'
        with self.assertRaises(ValueError):private_key(ring,self.secret)
    def test_envelope_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'contact.json').write_text('{}');b=seal(self.ring,p)
            b['ciphertext']=b['ciphertext'][:-8]+'AAAAAAAA'
            with self.assertRaises(InvalidTag):open_bundle(self.ring,b,self.secret,p/'out')
    def test_key_derivation_has_separate_purposes(self):
        self.assertNotEqual(derive(self.secret,b'private-key-wrapping'),derive(self.secret,b'private-review-artifact-encryption'))
    def test_short_or_missing_secret_fails(self):
        for secret in ['', 'short']:
            with self.assertRaises(ValueError):derive(secret,b'test')
    def test_bootstrap_does_not_rotate_an_existing_unreadable_key(self):
        with patch('greenhouse_private_v3.get_file',return_value=self.ring),patch.dict('os.environ',{'GREENHOUSE_WRAPPING_SECRET':'wrong-secret-long-enough'}),patch('greenhouse_private_v3.requests.put') as put:
            with self.assertRaises(ValueError):bootstrap()
            put.assert_not_called()

if __name__=='__main__':unittest.main()
