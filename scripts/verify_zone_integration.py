"""Real model + authenticated server ROI tests; no Firebase delivery is simulated."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8001')
    parser.add_argument('--credentials', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/evidence/features-20261110')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(args.credentials.read_text())
    session = requests.Session()
    login = session.post(args.base_url+'/api-token-auth/', data=credentials, timeout=20)
    login.raise_for_status(); session.headers['Authorization'] = 'JWT '+login.json()['token']
    env=os.environ.copy();env.update(PHOTO_SERVER=args.base_url,PHOTO_USERNAME=credentials['username'],PHOTO_PASSWORD=credentials['password'])
    before = session.get(args.base_url+'/api_root/Post/', timeout=20);before.raise_for_status()
    initial_ids = {p['id'] for p in before.json()}
    results=[]
    for name,rect,expected in [('outside',[0,0,1,.2],0),('inside',[.25,.2,.5,.85],1)]:
        body=dict(zip(['left','top','right','bottom'],rect),zone_enabled=True,zone_name='현관')
        response=session.patch(args.base_url+'/api/settings/',json=body,timeout=20);response.raise_for_status()
        output=ROOT/'YOLOv5/runs'/('roi-'+name)
        run=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'YOLOv5/detect.py'),'--source',str(ROOT/'YOLOv5/data/bus.jpg'),'--output',str(output)],env=env,capture_output=True,text=True)
        (args.output/('roi-'+name+'.txt')).write_text(run.stdout+run.stderr)
        run.check_returncode()
        record=json.loads((output/'results.json').read_text())
        uploaded=[item for frame in record['frames'] for item in frame['uploaded']]
        assert len(uploaded)==expected,(name,len(uploaded))
        shutil.copy2(output/'latest.jpg',args.output/('roi-'+name+'.jpg'))
        (args.output/('roi-'+name+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
        results.append({'case':name,'zone':body,'eligible_count':len(record['frames'][0]['eligible_detections']),'uploaded_count':len(uploaded),'post_ids':[u['post_id'] for u in uploaded]})
    after=session.get(args.base_url+'/api_root/Post/',timeout=20);after.raise_for_status()
    new=[p for p in after.json() if p['id'] not in initial_ids]
    assert len(new)==1 and new[0]['zone_name']=='현관'
    summary={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,'engine':'actual official YOLOv5n ONNX inference','cases':results,'new_post':new[0],'push':'Firebase not configured; no real push delivery claimed','result':'PASS'}
    (args.output/'roi-integration.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('PASS: server-configured ROI excludes all people outside, accepts one inside, creates exactly one real photo post.')


if __name__=='__main__':main()
