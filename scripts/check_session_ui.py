"""Manual synthetic browser regression. Requires playwright + installed Chromium.
Run from repo root: python scripts/check_session_ui.py
Uses dev auth on localhost, a temporary SQLite DB, no provider/model calls.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    env = dict(os.environ, SLATE_DEV_AUTH='1', SLATE_STATE_URL='sqlite:///'+tmp+'/state.db')
    proc = subprocess.Popen([os.environ.get("API_PYTHON", os.sys.executable), '-m', 'uvicorn', 'agents.slate_api.app:app', '--host', '127.0.0.1', '--port', '8014'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:8014/v1/config')
                break
            except Exception:
                time.sleep(.1)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.environ.get('CHROME_PATH', '/usr/bin/google-chrome'), args=['--no-sandbox'])
            for path in ('/', '/ai'):
                for result in ('success', 'error', 'unauthorized', 'network'):
                    page = browser.new_page()
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto('http://127.0.0.1:8014'+path)
                    page.locator('#devmail').fill('first@example.com')
                    page.locator('#devgo').click()
                    page.locator('#resume').fill('PRIVATE FIRST ACCOUNT\nSkills: Python, SQL')
                    page.locator('#parse').click()
                    page.wait_for_function('document.querySelector("#parsed").textContent.length>0')
                    delayed = []
                    endpoint = '**/v1/tailor' if path == '/' else '**/v1/tailor/ai'
                    page.route(endpoint, lambda route: delayed.append(route))
                    if path == '/':
                        page.locator('[data-j]').first.click()
                    else:
                        page.locator('#gen').click()
                    page.wait_for_timeout(50)
                    assert delayed
                    page.route('**/v1/force401', lambda route: route.fulfill(status=401, content_type='application/json', body='{"error":{"message":"Expired"}}'))
                    expr = "api('GET','/force401').catch(()=>{})" if path == '/' else "api('/force401','GET').catch(()=>{})"
                    page.evaluate(expr)
                    page.locator('#devmail').wait_for()
                    assert page.locator('#resume').input_value() == ''
                    assert page.locator('#parsed').inner_text() == ''
                    assert page.locator('#dres').input_value() == '' if path == '/' else page.locator('#dres').inner_text() == ''
                    page.locator('#devmail').fill('second@example.com')
                    page.locator('#devgo').click()
                    if result == 'network':
                        delayed[0].abort()
                    else:
                        status = {'success': 200, 'error': 500, 'unauthorized': 401}[result]
                        delayed[0].fulfill(status=status, content_type='application/json', body=json.dumps({'draftId':'STALE','tailoredResume':'PRIVATE FIRST ACCOUNT','coverNote':'OLD','skillGaps':[], 'error':{'message':'OLD FAILURE'}}))
                    page.wait_for_timeout(80)
                    assert page.evaluate('token()') == 'dev:second@example.com'
                    assert 'PRIVATE FIRST ACCOUNT' not in page.locator('body').inner_text()
                    assert 'OLD FAILURE' not in page.locator('body').inner_text()
                    assert page.evaluate('did' if path == '/' else 'draftId') is None
                    assert not errors, errors
                    if path == '/' and result == 'success':
                        page.screenshot(path=os.environ.get('SESSION_SCREENSHOT', '/tmp/slate-session-clean.png'), full_page=True)
                    page.close()
            browser.close()
        print('8 synthetic account-switch/late-response browser cases passed; server stopped')
    finally:
        proc.terminate()
        proc.wait(timeout=10)
