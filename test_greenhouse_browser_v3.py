"""Actual Chromium control tests, opt-in on CI; never submit to an employer."""
import os
import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from greenhouse_pipeline_v3 import fill_value, fill_form

@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'Set RUN_BROWSER_TESTS=1 with Chromium installed')
class BrowserTests(unittest.TestCase):
    def test_text_select_checkbox_file_and_required_discovery(self):
        with sync_playwright() as p:
            kwargs={'headless':True}
            if os.environ.get('CHROMIUM_PATH'):kwargs['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**kwargs);page=browser.new_page()
            page.set_content('''<form onsubmit="event.preventDefault();document.body.dataset.submitted='yes'">
              <label for="first_name">First Name</label><input id="first_name" required>
              <label for="sponsor">Sponsorship</label><select id="sponsor" required><option>No</option><option>Yes</option></select>
              <input id="consent" type="checkbox"><input id="resume" type="file" onchange="document.getElementById('file-label').textContent=this.files[0].name"><span id="file-label"></span>
              <input id="unexpected" required><button type="submit">Submit application</button></form>''')
            with tempfile.TemporaryDirectory() as d:
                file=Path(d)/'resume.txt';file.write_text('Test fixture only')
                answers=[{'name':'first_name','value':'Rao'},{'name':'sponsor','value':'Yes'},{'name':'consent','value':True},{'name':'resume','value':str(file)}]
                result=fill_form(page,{'answers':answers,'missing_required':[]})
                self.assertEqual(result['errors'],[])
                self.assertEqual(set(result['filled_fields']),{'first_name','sponsor','consent','resume'})
                self.assertEqual(result['unresolved_live_fields'][0]['id'],'unexpected')
                self.assertIsNone(page.locator('body').get_attribute('data-submitted'))
                self.assertFalse(result['submitted'])
            browser.close()

    def test_nonsearchable_greenhouse_dropdown_opens_before_selection(self):
        with sync_playwright() as p:
            kwargs={'headless':True}
            if os.environ.get('CHROMIUM_PATH'):kwargs['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**kwargs);page=browser.new_page()
            page.set_content('''<div class="select__control"><span id="selected"></span>
              <input id="sponsor" role="combobox" readonly onclick="document.getElementById('choices').hidden=false">
              <div id="choices" hidden><div role="option" onclick="document.getElementById('selected').textContent='Yes';document.getElementById('choices').hidden=true">Yes</div></div></div>''')
            self.assertTrue(fill_value(page,{'name':'sponsor','value':'Yes'}))
            self.assertEqual(page.locator('#selected').inner_text(),'Yes')
            browser.close()

    def test_country_abbreviation_requires_selected_option_readback(self):
        with sync_playwright() as p:
            kwargs={'headless':True}
            if os.environ.get('CHROMIUM_PATH'):kwargs['executable_path']=os.environ['CHROMIUM_PATH']
            browser=p.chromium.launch(**kwargs);page=browser.new_page()
            page.set_content('''<div class="select__control"><span>+1</span>
              <input id="country" role="combobox" readonly onclick="document.getElementById('choices').hidden=false">
              <div id="choices" hidden><div role="option" aria-selected="false" onclick="this.setAttribute('aria-selected','true');document.getElementById('choices').hidden=true">United States +1</div></div></div>''')
            self.assertTrue(fill_value(page,{'name':'country','value':'United States +1'}))
            self.assertEqual(page.get_by_role('option',name='United States +1').get_attribute('aria-selected'),'true')
            browser.close()

if __name__=='__main__':unittest.main()
