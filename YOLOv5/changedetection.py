"""Class-presence transitions and a durable HTTP upload outbox.

The lecture's ``0 -> 1`` rule is applied per class, not per person identity.
An unsuccessful HTTP request leaves the event on disk for a subsequent retry.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import cv2
import requests

LOG = logging.getLogger(__name__)


class ChangeDetection:
    def __init__(self, names, host=None, username=None, password=None,
                 monitored=None, session=None, timeout=15):
        self.names = list(names.values()) if isinstance(names, dict) else list(names)
        self.result_prev = [0] * len(self.names)
        self.host = (host or os.environ.get('PHOTO_SERVER', 'http://127.0.0.1:8000')).rstrip('/')
        if urlparse(self.host).scheme not in ('http', 'https'):
            raise ValueError('Server URL must start with http:// or https://')
        self.username = username or os.environ.get('PHOTO_USERNAME')
        self.password = password or os.environ.get('PHOTO_PASSWORD')
        if not self.username or not self.password:
            raise ValueError('Set PHOTO_USERNAME and PHOTO_PASSWORD before uploading')
        self.monitored = set(monitored if monitored is not None else ['person'])
        unknown = self.monitored.difference(self.names)
        if unknown:
            raise ValueError('Unknown monitored class: ' + ', '.join(sorted(unknown)))
        self.session = session or requests.Session()
        self.timeout = timeout
        self.token = None

    def authenticate(self):
        response = self.session.post(
            self.host + '/api-token-auth/',
            data={'username': self.username, 'password': self.password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.token = response.json()['token']
        # Tokens and passwords must never be included in logs.

    def add(self, names, detected_current, save_dir, image):
        current_names = list(names.values()) if isinstance(names, dict) else list(names)
        if current_names != self.names or len(detected_current) != len(self.names):
            raise ValueError('Class names and presence-vector length must remain stable')
        current = [int(bool(value)) for value in detected_current]
        appeared = [name for i, name in enumerate(self.names)
                    if self.result_prev[i] == 0 and current[i] == 1
                    and name in self.monitored]
        # Persist a transition before advancing state, so an image-write failure
        # does not silently consume the rising edge.
        if appeared:
            self._enqueue(save_dir, image, appeared)
        self.result_prev = current
        return self.flush(save_dir)

    def _enqueue(self, save_dir, image, appeared):
        now = datetime.now(timezone.utc)
        event_id = uuid.uuid4().hex
        directory = Path(save_dir) / 'outbox'
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / (event_id + '.jpg')
        preview = cv2.resize(image, (320, 240), interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(image_path), preview):
            raise OSError('Could not save detection image')
        event = {
            'event_id': event_id,
            'title': ', '.join(appeared),
            'text': '새 객체 출현: ' + ', '.join(appeared) + '\nEdge event: ' + event_id,
            'created_date': now.isoformat(),
            'published_date': now.isoformat(),
            'image_file': image_path.name,
        }
        target = directory / (event_id + '.json')
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(event, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)
        LOG.info('Queued new appearance: %s event=%s', ', '.join(appeared), event_id)

    def send(self, save_dir, image=None):
        """Flush stored events (legacy lecture method name)."""
        return self.flush(save_dir)

    def flush(self, save_dir):
        uploaded = []
        for manifest in sorted((Path(save_dir) / 'outbox').glob('*.json')):
            event = json.loads(manifest.read_text(encoding='utf-8'))
            # Bind every queued event to this deployment/account; the private
            # outbox is kept separately per server and username by the CLI.
            try:
                if not self.token:
                    self.authenticate()
                response = self._post(manifest.parent, event)
                if response.status_code in (401, 403):
                    self.authenticate()
                    response = self._post(manifest.parent, event)
                response.raise_for_status()
                post = response.json()
                if response.status_code != 201 or 'id' not in post:
                    raise ValueError('Upload API did not return a created post')
            except (requests.RequestException, KeyError, ValueError) as exc:
                # Only status / exception type, never a body containing secrets.
                LOG.warning('Upload pending event=%s (%s)', event['event_id'], type(exc).__name__)
                break
            uploaded.append({'event_id': event['event_id'], 'post_id': post['id']})
            # Keep the event JPEG as evidence after successful upload.
            archive = manifest.parent.parent / 'sent'
            archive.mkdir(parents=True, exist_ok=True)
            (manifest.parent / event['image_file']).replace(archive / event['image_file'])
            manifest.replace(archive / manifest.name)
            LOG.info('Created server post id=%s event=%s', post['id'], event['event_id'])
        return uploaded

    def _post(self, directory, event):
        data = {key: event[key] for key in ('title', 'text', 'created_date', 'published_date')}
        with (directory / event['image_file']).open('rb') as photo:
            return self.session.post(
                self.host + '/api_root/Post/', data=data,
                files={'image': (event['image_file'], photo, 'image/jpeg')},
                headers={'Authorization': 'JWT ' + self.token, 'Accept': 'application/json'},
                timeout=self.timeout,
            )
