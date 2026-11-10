"""Exercise the native ROI editor and verify the saved rectangle through the API."""
import argparse
import hashlib
import io
import json
import re
import shlex
import time
from pathlib import Path

import requests
from PIL import Image
from capture_android import adb, wait_for, locate, tap, capture, OUT, PACKAGE, ROOT


def type_text(value):
    adb('shell', 'input', 'text', shlex.quote(value.replace(' ', '%s')))


def visible(value, attribute='text'):
    for _ in range(5):
        node = locate(value, attribute)
        if node is not None:
            bounds = list(map(int,re.findall(r'\d+',node.attrib['bounds'])))
            if bounds[3] > bounds[1]: return node
        adb('shell','input','swipe','1040','2050','1040','1100','400')
    return wait_for(value,attribute)


def main():
    p=argparse.ArgumentParser();p.add_argument('--credentials',type=Path,required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:8001');p.add_argument('--app-url',default='http://10.0.2.2:8001')
    p.add_argument('--prefix',default='features-20261110');args=p.parse_args()
    credentials=json.loads(args.credentials.read_text());out=OUT/args.prefix;out.mkdir(parents=True,exist_ok=True)
    session=requests.Session();login=session.post(args.base_url+'/api-token-auth/',data=credentials,timeout=20);login.raise_for_status();session.headers['Authorization']='JWT '+login.json()['token']
    before=session.get(args.base_url+'/api/settings/',timeout=20);before.raise_for_status()
    image_response=session.get(before.json()['preview_image'],timeout=20);image_response.raise_for_status();photo=Image.open(io.BytesIO(image_response.content))
    adb('shell','pm','clear',PACKAGE);adb('shell','am','start','-n',PACKAGE+'/.MainActivity')
    tap(wait_for('서버 주소','content-desc'));time.sleep(.6);adb('shell','input','keyevent','123');adb('shell','input','keyevent',*(['67']*100));type_text(args.app_url);adb('shell','input','keyevent','4');time.sleep(.5)
    tap(wait_for('아이디','content-desc'));time.sleep(.6);type_text(credentials['username']);adb('shell','input','keyevent','61');time.sleep(.4);type_text(credentials['password']);adb('shell','input','keyevent','4');time.sleep(.5)
    assert wait_for('아이디','content-desc').attrib['text']==credentials['username'],'Login focus check failed; credentials not logged'
    tap(wait_for('로그인'));wait_for('감지 기록')
    tap(wait_for('감시 영역 · 알림 설정'));wait_for('지정한 영역만 감시');node=wait_for('감시 영역 사진 · 드래그해서 영역 지정','content-desc');time.sleep(1)
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']))
    scale=min((x2-x1)/photo.width,(y2-y1)/photo.height);w,h=photo.width*scale,photo.height*scale;left=x1+((x2-x1)-w)/2;top=y1+((y2-y1)-h)/2
    adb('shell','input','swipe',str(round(left+.18*w)),str(round(top+.18*h)),str(round(left+.58*w)),str(round(top+.9*h)),'650')
    capture(args.prefix+'/android-zone.png')
    enabled=locate('지정한 영역만 감시')
    if enabled is not None and enabled.attrib.get('checked')!='true':tap(enabled)
    tap(visible('감시 영역 저장'))
    wait_for('저장 완료 · YOLO가 다음 설정 조회 때 적용합니다.')
    visible('Firebase 연결 설정 대기 · google-services.json이 필요합니다.')
    capture(args.prefix+'/android-push-pending.png')
    after=session.get(args.base_url+'/api/settings/',timeout=20);after.raise_for_status();saved=after.json()
    assert saved['zone_enabled'] is True
    for key,value in zip(['left','top','right','bottom'],[.18,.18,.58,.9]):assert abs(saved[key]-value)<.03,(key,saved[key])
    assert saved['push']['configured'] is False
    result={'result':'PASS','app_url':args.app_url,'verified':['native_login','draw_region_on_actual_photo','save_to_authenticated_server','server_coordinates_match_drag','firebase_pending_state_visible'],
        'saved_settings':saved,'apk_sha256':hashlib.sha256((ROOT/'PhotoViewer/app/build/outputs/apk/debug/app-debug.apk').read_bytes()).hexdigest(),
        'push_delivery':'deferred by user; Firebase project not created; no delivery claimed'}
    (out/'android-zone-runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('PASS: native ROI drag saved to server; Firebase deferred state captured.')


if __name__=='__main__':main()
