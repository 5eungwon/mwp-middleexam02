"""Capture the actual web ROI editor and honest Firebase configuration status."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright


def main():
    p=argparse.ArgumentParser();p.add_argument('--credentials',type=Path,required=True)
    p.add_argument('--base-url',default='https://asdfgh0986.pythonanywhere.com')
    p.add_argument('--output',type=Path,default=Path('docs/evidence/features-20261110'));args=p.parse_args()
    credentials=json.loads(args.credentials.read_text());args.output.mkdir(parents=True,exist_ok=True)
    records=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1080})
        page.goto(args.base_url+'/accounts/login/',wait_until='networkidle')
        page.locator('[name=username]').fill(credentials['username']);page.locator('[name=password]').fill(credentials['password'])
        page.locator('button[type=submit]').click();page.wait_for_load_state('networkidle')
        assert '/accounts/login/' not in page.url
        for filename,path in [('web-zone.png','/settings/'),('web-push-pending.png','/api/settings/')]:
            response=page.goto(args.base_url+path,wait_until='networkidle');assert response.status==200
            if path=='/settings/':
                assert page.locator('#zone_enabled').is_checked()
                assert page.get_by_text('Firebase 연결 설정이 필요합니다.',exact=False).count()>0
            page.screenshot(path=str(args.output/filename),full_page=True)
            records.append({'file':filename,'url':page.url,'status':response.status})
        browser.close()
    (args.output/'web-captures.json').write_text(json.dumps({'captured_at_utc':datetime.now(timezone.utc).isoformat(),'captures':records},ensure_ascii=False,indent=2))
    print('Captured real cloud region settings and Firebase-pending API.')


if __name__=='__main__':main()
