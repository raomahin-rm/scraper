"""Inspect approved form validation without allowing a second submission request."""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.sync_api import sync_playwright
from greenhouse_pipeline_v3 import validate_approval, fetch_approval, assert_documents, fill_form, save


def main():
    p=argparse.ArgumentParser();p.add_argument('--packet',required=True);p.add_argument('--approval-comment',required=True);p.add_argument('--public-key',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    packet=json.loads(Path(a.packet).read_text());validate_approval(packet,fetch_approval(a.approval_comment));assert_documents(packet)
    blocked=[];gate={'closed':False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);context=browser.new_context()
        def guard(route):
            if gate['closed'] and route.request.method not in {'GET','HEAD','OPTIONS'}:
                blocked.append({'method':route.request.method,'host':urlparse(route.request.url).hostname})
                route.abort()
            else:route.continue_()
        context.route('**/*',guard);page=context.new_page();page.goto(packet['url'],wait_until='domcontentloaded',timeout=60000);page.locator('#first_name').wait_for()
        result=fill_form(page,packet,defer_files=False)
        before=page.locator('input,select,textarea').evaluate_all('''es=>es.filter(e=>e.willValidate&&!e.validity.valid).map(e=>({id:e.id,message:e.validationMessage}))''')
        # All non-read requests are now denied before exercising client validation.
        gate['closed']=True
        page.get_by_role('button',name='Submit application',exact=True).click()
        page.wait_for_timeout(1500)
        errors=page.locator('[id$="-error"], [role="alert"], .error-message').all_text_contents()
        invalid=page.locator('[aria-invalid="true"]').evaluate_all('es=>es.map(e=>({id:e.id,label:e.getAttribute("aria-label")}))')
        text=page.locator('body').inner_text()
        data={'fill':result,'native_invalid_before':before,'invalid_after':invalid,'errors':errors,'body_text':text,'blocked_requests':blocked,'no_second_submission_allowed':True}
        data['screenshot_png']=base64.b64encode(page.screenshot(full_page=True)).decode()
        browser.close()
    public=serialization.load_pem_public_key(Path(a.public_key).read_bytes());key=os.urandom(32);nonce=os.urandom(12);aad=b'greenhouse-validation-diagnostics-v1'
    wrapped=public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
    out={'wrapped_key':base64.b64encode(wrapped).decode(),'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(AESGCM(key).encrypt(nonce,json.dumps(data).encode(),aad)).decode()}
    save(a.output,out)
    print('Validation diagnostics encrypted; all outgoing mutation requests blocked before the diagnostic click')

if __name__=='__main__':main()
