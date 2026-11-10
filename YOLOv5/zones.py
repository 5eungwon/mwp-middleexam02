"""Normalized rectangular ROI, evaluated at each object's bottom center."""
import json
import logging
import math
import time
from pathlib import Path

LOG = logging.getLogger(__name__)


def validate_zone(values):
    rect = [float(values.get(key, default)) for key, default in [('left', 0), ('top', 0), ('right', 1), ('bottom', 1)]]
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in rect):
        raise ValueError('Zone coordinates must be finite numbers between 0 and 1')
    if rect[2] - rect[0] < .02 or rect[3] - rect[1] < .02:
        raise ValueError('Zone must have width and height of at least 2%')
    return dict(zip(['left', 'top', 'right', 'bottom'], rect),
                zone_enabled=bool(values.get('zone_enabled', False)),
                zone_name=str(values.get('zone_name', '현관'))[:80])


def eligible_detections(detections, image_shape, zone):
    if not zone['zone_enabled']:
        return list(detections)
    height, width = image_shape[:2]
    accepted = []
    for item in detections:
        x1, y1, x2, y2 = item['xyxy']
        x, y = (x1 + x2) / (2 * width), y2 / height
        if zone['left'] <= x <= zone['right'] and zone['top'] <= y <= zone['bottom']:
            accepted.append(item)
    return accepted


def draw_zone(image, zone):
    if not zone['zone_enabled']:
        return image
    import cv2
    output = image.copy()
    h, w = output.shape[:2]
    p1 = (round(zone['left'] * w), round(zone['top'] * h))
    p2 = (round(zone['right'] * w), round(zone['bottom'] * h))
    cv2.rectangle(output, p1, p2, (40, 230, 140), max(2, w // 300))
    cv2.putText(output, 'MONITORED ZONE', (p1[0] + 5, max(20, p1[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX, .6, (40, 230, 140), 2)
    return output


class RemoteZone:
    def __init__(self, detector, directory, interval=5):
        self.detector = detector
        self.path = Path(directory) / 'zone-settings.json'
        self.interval = interval
        self.last_attempt = -float('inf')
        self.current = validate_zone(json.loads(self.path.read_text())) if self.path.exists() else None

    def get(self):
        now = time.monotonic()
        if now - self.last_attempt < self.interval and self.current is not None:
            return self.current
        self.last_attempt = now
        try:
            if not self.detector.token:
                self.detector.authenticate()
            def request():
                return self.detector.session.get(self.detector.host + '/api/settings/',
                    headers={'Authorization': 'JWT ' + self.detector.token}, timeout=self.detector.timeout)
            response = request()
            if response.status_code in (401, 403):
                self.detector.authenticate()
                response = request()
            response.raise_for_status()
            self.current = validate_zone(response.json())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.current, ensure_ascii=False))
            temporary.replace(self.path)
        except Exception as error:
            LOG.warning('Region settings unavailable (%s)', type(error).__name__)
            if self.current is None:
                raise RuntimeError('No verified zone configuration. Check the server connection before uploading.') from None
        return self.current
