"""Encrypt private application artifacts before publishing to GitHub Actions."""
import argparse
import base64
import io
import os
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def key():
    raw = base64.b64decode(os.environ['APPLICATION_PACKET_KEY'], validate=True)
    if len(raw) != 32:
        raise ValueError('APPLICATION_PACKET_KEY must be a base64-encoded 32-byte key')
    return raw

def pack(source, destination):
    stream=io.BytesIO()
    source=Path(source)
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for path in source.rglob('*'):
            if path.is_file() and path.suffix in {'.json','.md','.txt'}:
                z.write(path,path.relative_to(source))
    nonce=os.urandom(12)
    Path(destination).parent.mkdir(parents=True,exist_ok=True)
    Path(destination).write_bytes(nonce+AESGCM(key()).encrypt(nonce,stream.getvalue(),b'greenhouse-v3'))

def unpack(source,destination):
    data=Path(source).read_bytes()
    plaintext=AESGCM(key()).decrypt(data[:12],data[12:],b'greenhouse-v3')
    root=Path(destination).resolve()
    with zipfile.ZipFile(io.BytesIO(plaintext)) as z:
        for name in z.namelist():
            if not (root/name).resolve().is_relative_to(root):
                raise ValueError('Unsafe archive path')
        z.extractall(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','unpack']);p.add_argument('source');p.add_argument('destination');a=p.parse_args()
    (pack if a.action=='pack' else unpack)(a.source,a.destination)
