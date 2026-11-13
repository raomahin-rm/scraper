"""Envelope-encrypted private application inputs; no plaintext repository files.

The Actions runner owns the RSA private key. An existing Actions secret wraps it
using a purpose-specific HKDF key. Only the public key leaves the runner in
plaintext; the agent seals existing materials to it. Credential values are never
returned or logged. The secret is used locally for encryption, never for mail.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import zipfile
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

REPO = 'raomahin-rm/scraper'
BRANCH = 'application-submission-ledger'
KEYRING = 'private-materials/keyring.json'
MATERIALS = 'private-materials/inputs.enc.json'
AAD = b'greenhouse-private-inputs-v1'
ALLOWED = {'contact.json', 'overrides.json', 'resume.pdf', 'cover-letter.txt', 'Rao_Mahin_Resume.pdf', 'Rao_Mahin_Cover_Letter_Via.pdf'}
MAX_SIZE = 20 * 1024 * 1024


def derive(secret, purpose):
    if not secret or len(secret) < 16:
        raise ValueError('An existing strong Actions wrapping secret is required')
    return HKDF(algorithm=hashes.SHA256(), length=32,
                salt=b'raomahin-rm/scraper/greenhouse/v1', info=purpose).derive(secret.encode())


def encode(value):
    return base64.b64encode(value).decode('ascii')


def decode(value):
    return base64.b64decode(value, validate=True)


def make_keyring(secret):
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.BestAvailableEncryption(derive(secret, b'private-key-wrapping')))
    return {'version': 1, 'public_pem': public.decode(), 'key_id': hashlib.sha256(public).hexdigest(),
            'encrypted_private_pem': private.decode()}


def private_key(ring, secret):
    public = ring['public_pem'].encode()
    if ring.get('version') != 1 or hashlib.sha256(public).hexdigest() != ring['key_id']:
        raise ValueError('Keyring version or fingerprint mismatch')
    key = serialization.load_pem_private_key(ring['encrypted_private_pem'].encode(),
                                            password=derive(secret, b'private-key-wrapping'))
    actual = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    if actual != public:
        raise ValueError('Keyring public and private keys differ')
    return key


def seal(ring, folder):
    public = ring['public_pem'].encode()
    if hashlib.sha256(public).hexdigest() != ring['key_id']:
        raise ValueError('Public key fingerprint mismatch')
    key = serialization.load_pem_public_key(public)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(ALLOWED):
            p = Path(folder) / name
            if p.is_file():
                if p.stat().st_size > MAX_SIZE:
                    raise ValueError('Private material is too large')
                archive.writestr(name, p.read_bytes())
    data_key, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    wrapped = key.encrypt(data_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=AAD))
    return {'version': 1, 'key_id': ring['key_id'], 'wrapped_key': encode(wrapped), 'nonce': encode(nonce),
            'ciphertext': encode(AESGCM(data_key).encrypt(nonce, stream.getvalue(), AAD))}


def open_bundle(ring, bundle, secret, destination):
    if bundle.get('version') != 1 or bundle['key_id'] != ring['key_id']:
        raise ValueError('Private material key/version mismatch')
    key = private_key(ring, secret)
    data_key = key.decrypt(decode(bundle['wrapped_key']), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=AAD))
    plaintext = AESGCM(data_key).decrypt(decode(bundle['nonce']), decode(bundle['ciphertext']), AAD)
    with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not set(names).issubset(ALLOWED) or sum(x.file_size for x in archive.infolist()) > MAX_SIZE:
            raise ValueError('Unexpected or oversized private archive')
        # Validate all payloads before writing any private file.
        payloads = {name: archive.read(name) for name in names}
        for name in ('contact.json', 'overrides.json'):
            if name in payloads and not isinstance(json.loads(payloads[name]), dict):
                raise ValueError('Private JSON inputs must be objects')
        if any(name.endswith('.pdf') and not content.startswith(b'%PDF-') for name, content in payloads.items()):
            raise ValueError('Application document is not a PDF')
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name, content in payloads.items():
            path = root / name
            path.write_bytes(content)
            path.chmod(0o600)
    return sorted(payloads)


def headers():
    token = os.environ.get('GH_TOKEN')
    if not token:
        raise ValueError('GitHub runner token is required')
    return {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'}


def get_file(path):
    r = requests.get(f'https://api.github.com/repos/{REPO}/contents/{path}', params={'ref': BRANCH}, headers=headers(), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return json.loads(decode(''.join(r.json()['content'].split())))


def bootstrap():
    secret = os.environ.get('GREENHOUSE_WRAPPING_SECRET', '')
    ring = get_file(KEYRING)
    if ring is None:
        # An absent branch or inaccessible ledger is not permission to replace a key.
        r = requests.get(f'https://api.github.com/repos/{REPO}/git/ref/heads/{BRANCH}', headers=headers(), timeout=30)
        r.raise_for_status()
        ring = make_keyring(secret)
        r = requests.put(f'https://api.github.com/repos/{REPO}/contents/{KEYRING}', headers=headers(), timeout=30,
                         json={'branch': BRANCH, 'message': 'Initialize wrapped application-material key',
                               'content': encode((json.dumps(ring, indent=2) + '\n').encode())})
        r.raise_for_status()  # concurrent first creation fails closed; never overwrite
    private_key(ring, secret)
    env_file = os.environ.get('GITHUB_ENV')
    if not env_file:
        raise ValueError('Bootstrap must run in GitHub Actions')
    packet_key = encode(derive(secret, b'private-review-artifact-encryption'))
    print('::add-mask::' + packet_key)
    with open(env_file, 'a') as output:
        output.write('APPLICATION_PACKET_KEY=' + packet_key + '\n')
    print('Application encryption key ready: ' + ring['key_id'])


def restore(destination, allow_empty=False):
    ring, bundle = get_file(KEYRING), get_file(MATERIALS)
    if ring is None:
        raise ValueError('Application keyring is unavailable')
    if bundle is None:
        if not allow_empty:
            raise ValueError('Encrypted application inputs have not been supplied')
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        for name in ('contact.json', 'overrides.json'):
            (root/name).write_text('{}')
        print('No sealed private inputs yet; safe public smoke test only')
        return
    names = open_bundle(ring, bundle, os.environ.get('GREENHOUSE_WRAPPING_SECRET', ''), destination)
    print('Restored encrypted private inputs: ' + ', '.join(names))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['bootstrap', 'restore', 'seal'])
    p.add_argument('--destination', default='runtime/private')
    p.add_argument('--source')
    p.add_argument('--keyring')
    p.add_argument('--output')
    p.add_argument('--allow-empty', action='store_true')
    a = p.parse_args()
    if a.action == 'bootstrap':
        bootstrap()
    elif a.action == 'restore':
        restore(a.destination, a.allow_empty)
    else:
        if not a.source or not a.keyring or not a.output:
            p.error('seal requires --source, --keyring, --output')
        ring = json.loads(Path(a.keyring).read_text())
        # Seal only uses the public key, even if the record includes encrypted private bytes.
        sealed = seal(ring, a.source)
        Path(a.output).write_text(json.dumps(sealed, indent=2) + '\n')
        print('Private inputs sealed to public key ' + ring['key_id'])

if __name__ == '__main__':
    main()
