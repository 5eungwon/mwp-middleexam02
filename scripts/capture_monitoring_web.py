"""Exercise the real web switch and verify the API state before capturing."""
import argparse
import json
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8002')
    parser.add_argument('--output', type=Path, default=Path('docs/evidence/monitoring-20261110/local-web'))
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    auth = session.post(args.base_url+'/api-token-auth/', data=credentials, timeout=30)
    auth.raise_for_status()
    session.headers['Authorization'] = 'JWT '+auth.json()['token']
    response = session.get(args.base_url+'/api/settings/', timeout=30)
    response.raise_for_status()
    initial = response.json()['monitoring_enabled']
    cases = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1080})
            page.goto(args.base_url+'/accounts/login/')
            page.locator('[name=username]').fill(credentials['username'])
            page.locator('[name=password]').fill(credentials['password'])
            page.locator('button[type=submit]').click()
            page.wait_for_load_state('networkidle')
            page.goto(args.base_url+'/settings/', wait_until='networkidle')
            for enabled, label in [(False,'off'),(True,'on')]:
                page.locator('#monitoring_enabled').set_checked(enabled)
                expected = '감시 ON · 새 객체 출현을 기록합니다.' if enabled else '감시 OFF · 새 감지 사진 등록이 중지되었습니다.'
                page.wait_for_function('(text)=>document.querySelector("#monitoring-status").textContent===text', arg=expected)
                response = session.get(args.base_url+'/api/settings/', timeout=30)
                response.raise_for_status()
                assert response.json()['monitoring_enabled'] is enabled
                page.screenshot(path=str(args.output/('web-monitoring-'+label+'.png')), full_page=True)
                cases.append({'requested':enabled,'server_value':enabled,'result':'PASS'})
            browser.close()
    finally:
        session.patch(args.base_url+'/api/settings/',json={'monitoring_enabled':initial},timeout=30).raise_for_status()
    (args.output/'web-monitoring-runtime.json').write_text(json.dumps({'result':'PASS','base_url':args.base_url,'cases':cases,'original_monitoring_state_restored':True},ensure_ascii=False,indent=2))
    print('PASS: real web switch OFF/ON persisted to API.')


if __name__ == '__main__':
    main()
