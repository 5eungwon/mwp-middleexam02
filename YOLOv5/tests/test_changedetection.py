import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from changedetection import ChangeDetection


class Response:
    def __init__(self, status=201, data=None):
        self.status_code = status
        self.data = data or {'id': 1}

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class Session:
    def __init__(self):
        self.uploads = []
        self.failures = []
        self.logins = 0

    def post(self, url, **kwargs):
        if url.endswith('/api-token-auth/'):
            self.logins += 1
            return Response(200, {'token': 'test-token'})
        if self.failures:
            failure = self.failures.pop(0)
            if isinstance(failure, Exception):
                raise failure
            return Response(failure)
        image = kwargs['files']['image'][1]
        self.uploads.append({'data': kwargs['data'], 'image': image.read(),
                             'authorization': kwargs['headers']['Authorization']})
        return Response(201, {'id': len(self.uploads)})


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.session = Session()
        self.detector = self.create_detector()
        self.image = np.zeros((120, 160, 3), dtype=np.uint8)

    def create_detector(self):
        return ChangeDetection(['person', 'bus'], 'http://localhost:8000',
                               'unit-user', 'unit-secret', session=self.session)

    def add(self, presence):
        return self.detector.add(['person', 'bus'], presence, self.directory, self.image)

    def test_new_presence_uploads_once_and_held_presence_is_suppressed(self):
        self.assertEqual(self.add([0, 0]), [])
        self.assertEqual(len(self.add([1, 0])), 1)
        self.assertEqual(self.add([1, 0]), [])
        self.assertEqual(len(self.session.uploads), 1)
        self.assertEqual(self.session.uploads[0]['data']['title'], 'person')
        self.assertTrue(self.session.uploads[0]['image'].startswith(b'\xff\xd8'))
        self.assertEqual(self.session.uploads[0]['authorization'], 'JWT test-token')

    def test_disappearance_then_reappearance_uploads_again(self):
        self.add([1, 0])
        self.add([0, 0])
        self.add([1, 0])
        self.assertEqual(len(self.session.uploads), 2)

    def test_non_monitored_class_does_not_upload(self):
        self.add([0, 1])
        self.assertEqual(self.session.uploads, [])

    def test_failed_upload_is_retried_when_presence_is_held(self):
        self.session.failures = [requests.ConnectionError('offline')]
        self.assertEqual(self.add([1, 0]), [])
        self.assertEqual(len(list((self.directory / 'outbox').glob('*.json'))), 1)
        self.assertEqual(len(self.add([1, 0])), 1)
        self.assertEqual(len(self.session.uploads), 1)
        self.assertEqual(list((self.directory / 'outbox').glob('*.json')), [])

    def test_restart_can_flush_persisted_event_without_a_new_transition(self):
        self.session.failures = [503]
        self.add([1, 0])
        restarted = self.create_detector()
        self.assertEqual(len(restarted.flush(self.directory)), 1)
        self.assertEqual(len(self.session.uploads), 1)

    def test_expired_token_is_refreshed_once(self):
        self.session.failures = [401]
        self.add([1, 0])
        self.assertEqual(self.session.logins, 2)
        self.assertEqual(len(self.session.uploads), 1)

    def test_mismatched_presence_vector_rejected(self):
        with self.assertRaises(ValueError):
            self.add([1])

    def test_instances_do_not_share_previous_state(self):
        self.add([1, 0])
        another = self.create_detector()
        another.add(['person', 'bus'], [1, 0], self.directory, self.image)
        self.assertEqual(len(self.session.uploads), 2)


if __name__ == '__main__':
    unittest.main()
