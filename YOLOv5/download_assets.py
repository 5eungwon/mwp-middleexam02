#!/usr/bin/env python3
"""Download checksum-pinned assets from the official YOLOv5 v7.0 release."""
import hashlib
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ASSETS = {
    'models/yolov5n.onnx': (
        'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx',
        '04f0e55c26f58d17145b36045780fe1250d5bd2187543e11568e5141d05b3262'),
    'data/bus.jpg': (
        'https://raw.githubusercontent.com/ultralytics/yolov5/v7.0/data/images/bus.jpg',
        '33b198a1d2839bb9ac4c65d61f9e852196793cae9a0781360859425f6022b69c'),
    'data/coco.yaml': (
        'https://raw.githubusercontent.com/ultralytics/yolov5/v7.0/data/coco128.yaml',
        '41fa8524f39a2d9b8324c80622739b903444a62aa3bf1b66762a87b0da7a7574'),
    'UPSTREAM-LICENSE.txt': (
        'https://raw.githubusercontent.com/ultralytics/yolov5/v7.0/LICENSE',
        '7fa7e56c0db71105f4b59a6a0ac40225eb059876f85cd380383f7d7a066e68be'),
}


def main():
    for relative, (url, checksum) in ASSETS.items():
        target = ROOT / relative
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == checksum:
            print('Verified ' + relative)
            continue
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != checksum:
            raise ValueError('Checksum mismatch: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_bytes(response.content)
        temporary.replace(target)
        print('Downloaded and verified ' + relative)


if __name__ == '__main__':
    main()
