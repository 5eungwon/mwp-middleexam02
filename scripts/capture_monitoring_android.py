"""Use the native switch, then verify OFF/ON persistence through the live API."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import requests
from capture_android import adb, wait_for, tap, capture, OUT, PACKAGE, ROOT
from capture_zone_android import type_text, visible


def main():
    p=argparse.ArgumentParser();p.add_argument('--credentials',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8002');p.add_argument('--app-url',default='http://10.0.2.2:8002')
    p.add_argument('--prefix',default='monitoring-20261110/local-android');args=p.parse_args()
    credentials=json.loads(args.credentials.read_text());out=OUT/args.prefix;out.mkdir(parents=True,exist_ok=True)
    session=requests.Session();login=session.post(args.base_url+'/api-token-auth/',data=credentials,timeout=20);login.raise_for_status();session.headers['Authorization']='JWT '+login.json()['token']
    before=session.get(args.base_url+'/api/settings/',timeout=20);before.raise_for_status();initial=before.json()['monitoring_enabled']
    adb('shell','pm','clear',PACKAGE);adb('shell','am','start','-n',PACKAGE+'/.MainActivity')
    tap(wait_for('서버 주소','content-desc'));time.sleep(.6);adb('shell','input','keyevent','123');adb('shell','input','keyevent',*(['67']*100));type_text(args.app_url);adb('shell','input','keyevent','4');time.sleep(.5)
    tap(wait_for('아이디','content-desc'));time.sleep(.6);type_text(credentials['username']);adb('shell','input','keyevent','61');time.sleep(.4);type_text(credentials['password']);adb('shell','input','keyevent','4');time.sleep(.5)
    assert wait_for('아이디','content-desc').attrib['text']==credentials['username'],'Login focus check failed; credentials not logged'
    tap(wait_for('로그인'));wait_for('감지 기록');tap(wait_for('감시 영역 · 원격 제어'))
    wait_for('지정한 영역만 감시');time.sleep(.8);capture(args.prefix+'/android-zone.png')
    cases=[]
    try:
        for enabled,label in [(False,'off'),(True,'on')]:
            node=visible('감시 작동','content-desc')
            if (node.attrib.get('checked')=='true')!=enabled:tap(node)
            wait_for('감시 ON · YOLO가 다음 설정 조회 때 감지를 재개합니다.' if enabled else '감시 OFF · 새 감지 사진 등록이 중지되었습니다.')
            response=session.get(args.base_url+'/api/settings/',timeout=20);response.raise_for_status()
            assert response.json()['monitoring_enabled'] is enabled
            capture(args.prefix+'/android-monitoring-'+label+'.png')
            cases.append({'requested':enabled,'server_value':response.json()['monitoring_enabled'],'result':'PASS'})
    finally:
        session.patch(args.base_url+'/api/settings/',json={'monitoring_enabled':initial},timeout=20).raise_for_status()
    installed=adb('shell','pm','path',PACKAGE).strip().removeprefix('package:')
    installed_sha=hashlib.sha256(adb('exec-out','cat',installed,binary=True)).hexdigest()
    apk=ROOT/'PhotoViewer/app/build/outputs/apk/debug/app-debug.apk';assert installed_sha==hashlib.sha256(apk.read_bytes()).hexdigest()
    report={'result':'PASS','app_url':args.app_url,'cases':cases,'installed_apk_matches_build':True,'installed_apk_sha256':installed_sha,
        'original_monitoring_state':initial,'initial_monitoring_state_restored':True,'firebase_required':False,'verified':['native_login','native_settings','off_persisted_to_server','on_persisted_to_server','same_tested_apk']}
    (out/'android-monitoring-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('PASS: actual Android switch OFF/ON saved to server; no Firebase setup required.')


if __name__=='__main__':main()
