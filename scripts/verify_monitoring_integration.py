"""Verify ON -> OFF -> ON using one actual YOLO detector and a live server."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import cv2
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'YOLOv5'))
from changedetection import ChangeDetection
from coco import NAMES
from detect import YoloV5, annotate
from zones import RemoteZone, eligible_detections, draw_zone


def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8002')
    p.add_argument('--credentials',required=True,type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'docs/evidence/monitoring-20261110/local')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    credentials=json.loads(args.credentials.read_text());session=requests.Session()
    login=session.post(args.base_url+'/api-token-auth/',data=credentials,timeout=20);login.raise_for_status()
    session.headers['Authorization']='JWT '+login.json()['token']
    original=session.get(args.base_url+'/api/settings/',timeout=20);original.raise_for_status()
    restore={k:original.json()[k] for k in ['monitoring_enabled','zone_enabled']}
    listing=session.get(args.base_url+'/api_root/Post/',timeout=20);listing.raise_for_status();initial={post['id'] for post in listing.json()}
    model=YoloV5(ROOT/'YOLOv5/models/yolov5n.onnx');image=cv2.imread(str(ROOT/'YOLOv5/data/bus.jpg'))
    detector=ChangeDetection(NAMES,args.base_url,credentials['username'],credentials['password'])
    cases=[]
    try:
        session.patch(args.base_url+'/api/settings/',json={'zone_enabled':False},timeout=20).raise_for_status()
        with tempfile.TemporaryDirectory() as temporary:
            remote=RemoteZone(detector,temporary,interval=1)
            for name,enabled,expected in [('on_initial',True,1),('off',False,0),('on_resumed',True,1)]:
                changed=session.patch(args.base_url+'/api/settings/',json={'monitoring_enabled':enabled},timeout=20);changed.raise_for_status()
                remote.last_attempt=-float('inf');settings=remote.get();assert settings['monitoring_enabled'] is enabled
                detector.set_monitoring(enabled)
                predictions=model.infer(image) if enabled else []
                accepted=eligible_detections(predictions,image.shape,settings);presence=[0]*len(NAMES)
                for item in accepted:presence[item['class_id']]=1
                photo=annotate(image,predictions,{'person'})
                uploaded=detector.add(NAMES,presence,temporary,photo)
                assert len(uploaded)==expected,(name,uploaded)
                assert detector.add(NAMES,presence,temporary,photo)==[],'Held presence must not duplicate'
                cv2.imwrite(str(args.output/(name+'.jpg')),draw_zone(photo,settings))
                record={'phase':name,'monitoring_enabled':enabled,'actual_model_executed':enabled,
                    'detections':predictions,'uploads':uploaded,'held_presence_uploads':0}
                if not enabled:
                    with (ROOT/'YOLOv5/data/bus.jpg').open('rb') as f:
                        rejected=session.post(args.base_url+'/api_root/Post/',data={'title':'blocked-test'},files={'image':('bus.jpg',f,'image/jpeg')},timeout=30)
                    assert rejected.status_code==423
                    record['stale_client_registration_status']=423
                    env=os.environ.copy();env.update(PHOTO_USERNAME=credentials['username'],PHOTO_PASSWORD=credentials['password'],PHOTO_SERVER=args.base_url)
                    run=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'YOLOv5/detect.py'),'--source',str(ROOT/'YOLOv5/data/bus.jpg'),'--zone','0','0','1','1','--output',str(Path(temporary)/'cli')],env=env,capture_output=True,text=True)
                    run.check_returncode();cli=json.loads((Path(temporary)/'cli/results.json').read_text())
                    assert not cli['frames'][0]['zone']['monitoring_enabled'] and not cli['frames'][0]['uploaded']
                    record['cli_roi_override_cannot_bypass_remote_off']=True
                cases.append(record)
    finally:
        session.patch(args.base_url+'/api/settings/',json=restore,timeout=20).raise_for_status()
    after=session.get(args.base_url+'/api_root/Post/',timeout=20);after.raise_for_status()
    created=[post for post in after.json() if post['id'] not in initial]
    assert len(created)==2
    result={'result':'PASS','captured_at_utc':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,
        'same_detector_instance':True,'cases':cases,'new_post_ids':[post['id'] for post in created],
        'original_settings_restored':restore,'input':'official public bus.jpg still image; no physical camera test'}
    (args.output/'monitoring-integration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('PASS: same detector ON=1 / OFF=0 / ON=1; held presence suppressed; stale clients blocked423; ROI override cannot bypass OFF.')


if __name__=='__main__':main()
