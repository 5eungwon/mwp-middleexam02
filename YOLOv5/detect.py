#!/usr/bin/env python3
"""Run official YOLOv5n ONNX inference and upload class-appearance events."""
import argparse
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from changedetection import ChangeDetection
from coco import NAMES

ROOT = Path(__file__).resolve().parent


class YoloV5:
    def __init__(self, model, confidence=0.40, iou=0.45, size=640):
        if not Path(model).is_file():
            raise FileNotFoundError('Model missing. Run python YOLOv5/download_assets.py first')
        self.net = cv2.dnn.readNetFromONNX(str(model))
        self.confidence = confidence
        self.iou = iou
        self.size = size

    def infer(self, image):
        height, width = image.shape[:2]
        ratio = min(self.size / width, self.size / height)
        scaled_w, scaled_h = round(width * ratio), round(height * ratio)
        pad_x = (self.size - scaled_w) // 2
        pad_y = (self.size - scaled_h) // 2
        canvas = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + scaled_h, pad_x:pad_x + scaled_w] = cv2.resize(image, (scaled_w, scaled_h))
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (self.size, self.size), swapRB=True)
        self.net.setInput(blob)
        rows = self.net.forward()[0]
        if rows.ndim != 2 or rows.shape[1] != 85:
            raise ValueError('Expected a YOLOv5 COCO ONNX output shaped [1, N, 85]')
        candidates = {}
        for row in rows:
            class_id = int(np.argmax(row[5:]))
            confidence = float(row[4] * row[5 + class_id])
            if confidence < self.confidence:
                continue
            cx, cy, box_w, box_h = [float(value) for value in row[:4]]
            x1 = max(0, min(width, (cx - box_w / 2 - pad_x) / ratio))
            y1 = max(0, min(height, (cy - box_h / 2 - pad_y) / ratio))
            x2 = max(0, min(width, (cx + box_w / 2 - pad_x) / ratio))
            y2 = max(0, min(height, (cy + box_h / 2 - pad_y) / ratio))
            if x2 <= x1 or y2 <= y1:
                continue
            candidates.setdefault(class_id, []).append(([x1, y1, x2 - x1, y2 - y1], confidence))
        detections = []
        for class_id, items in candidates.items():
            boxes, scores = zip(*items)
            # Class-wise NMS prevents one class suppressing a different class.
            indices = cv2.dnn.NMSBoxes(list(boxes), list(scores), self.confidence, self.iou)
            for index in np.asarray(indices).reshape(-1):
                x, y, box_w, box_h = boxes[int(index)]
                detections.append({
                    'class_id': class_id, 'name': NAMES[class_id],
                    'confidence': round(scores[int(index)], 6),
                    'xyxy': [round(x), round(y), round(x + box_w), round(y + box_h)],
                })
        return sorted(detections, key=lambda item: -item['confidence'])


def annotate(image, detections, monitored):
    output = image.copy()
    for detection in detections:
        x1, y1, x2, y2 = detection['xyxy']
        color = (80, 80, 245) if detection['name'] in monitored else (120, 210, 40)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 3)
        label = '{} {:.0%}'.format(detection['name'], detection['confidence'])
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .65, 2)
        label_y = max(label_h + 8, y1)
        cv2.rectangle(output, (x1, label_y - label_h - 8), (min(output.shape[1], x1 + label_w + 8), label_y), color, -1)
        cv2.putText(output, label, (x1 + 4, label_y - 5), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 2)
    return output


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='0', help='Camera index, image/video path, or RTSP URL')
    parser.add_argument('--weights', type=Path, default=ROOT / 'models/yolov5n.onnx')
    parser.add_argument('--conf-thres', type=float, default=.40)
    parser.add_argument('--iou-thres', type=float, default=.45)
    parser.add_argument('--classes', nargs='+', default=['person'], help='Monitored COCO names, or all')
    parser.add_argument('--host', default=os.environ.get('PHOTO_SERVER', 'http://127.0.0.1:8000'))
    parser.add_argument('--username', default=os.environ.get('PHOTO_USERNAME'))
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/detect')
    parser.add_argument('--max-frames', type=int, default=0, help='0 means no frame limit')
    parser.add_argument('--no-upload', action='store_true', help='Only local inference; no server requests')
    args = parser.parse_args()
    if not 0 < args.conf_thres <= 1 or not 0 < args.iou_thres <= 1:
        parser.error('Thresholds must be greater than 0 and at most 1')
    if args.max_frames < 0:
        parser.error('--max-frames must be at least 0')
    if args.classes == ['all']:
        args.classes = list(NAMES)
    if set(args.classes).difference(NAMES):
        parser.error('--classes contains a name absent from COCO')
    return args


def main():
    args = arguments()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    model = YoloV5(args.weights, args.conf_thres, args.iou_thres)
    args.output.mkdir(parents=True, exist_ok=True)
    detector = None
    # An outbox belongs to one destination/account, so a later account switch
    # cannot upload an earlier user's pending events into another user's feed.
    account = hashlib.sha256((args.host.rstrip('/') + '\0' + (args.username or '')).encode()).hexdigest()[:16]
    outbox = args.output / ('delivery-' + account)
    if not args.no_upload:
        detector = ChangeDetection(NAMES, args.host, args.username, monitored=args.classes)
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    is_image = Path(args.source).suffix.lower() in image_extensions and Path(args.source).is_file()
    capture = None
    if is_image:
        image = cv2.imread(args.source)
        if image is None:
            raise ValueError('Cannot decode source image')
    else:
        capture = cv2.VideoCapture(int(args.source) if args.source.isdecimal() else args.source)
        if not capture.isOpened():
            raise OSError('Cannot open camera/video source')
    records = []
    processed = 0
    started = datetime.now(timezone.utc).isoformat()
    try:
        while True:
            if capture is not None:
                ok, image = capture.read()
                if not ok:
                    break
            tick = time.perf_counter()
            detections = model.infer(image)
            elapsed = round((time.perf_counter() - tick) * 1000, 2)
            annotated = annotate(image, detections, set(args.classes))
            cv2.imwrite(str(args.output / 'latest.jpg'), annotated)
            presence = [0] * len(NAMES)
            for detection in detections:
                presence[detection['class_id']] = 1
            uploaded = detector.add(NAMES, presence, outbox, annotated) if detector else []
            processed += 1
            record = {'frame': processed, 'inference_ms': elapsed,
                      'detections': detections, 'uploaded': uploaded}
            records.append(record)
            # Keep a bounded in-memory report for long running camera streams.
            if len(records) > 1000:
                records.pop(0)
            logging.info('frame=%s detected=%s uploaded=%s inference_ms=%s',
                         record['frame'], ','.join(item['name'] for item in detections),
                         len(uploaded), elapsed)
            if is_image or (args.max_frames and record['frame'] >= args.max_frames):
                break
    finally:
        if capture is not None:
            capture.release()
    pending = len(list((outbox / 'outbox').glob('*.json'))) if detector else 0
    report = {
        'started_at': started, 'engine': 'OpenCV DNN / official YOLOv5n v7.0 ONNX',
        'source': args.source, 'weights_sha256': hashlib.sha256(args.weights.read_bytes()).hexdigest(),
        'confidence_threshold': args.conf_thres, 'iou_threshold': args.iou_thres,
        'monitored_classes': args.classes, 'upload_enabled': detector is not None,
        'pending_uploads': pending, 'processed_frames': processed, 'frames': records,
    }
    (args.output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'processed_frames': processed, 'pending_uploads': pending,
                      'results': str(args.output / 'results.json')}, ensure_ascii=False))
    return 2 if pending else 0


if __name__ == '__main__':
    raise SystemExit(main())
