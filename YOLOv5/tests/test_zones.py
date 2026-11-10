import sys
import unittest
import tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zones import validate_zone, eligible_detections, RemoteZone
from changedetection import ChangeDetection
from test_changedetection import Session


class ZoneTests(unittest.TestCase):
    def setUp(self):
        self.zone = validate_zone({'zone_enabled': True, 'left': .2, 'top': .2, 'right': .8, 'bottom': .9})
        self.inside = {'class_id': 0, 'name': 'person', 'xyxy': [30, 20, 50, 80]}
        self.outside = {'class_id': 0, 'name': 'person', 'xyxy': [80, 20, 100, 80]}

    def test_bottom_center_and_disabled_full_frame(self):
        detections = [self.inside, self.outside]
        self.assertEqual(eligible_detections(detections, (100, 100, 3), self.zone), [self.inside])
        self.zone['zone_enabled'] = False
        self.assertEqual(eligible_detections(detections, (100, 100, 3), self.zone), detections)

    def test_reject_invalid_regions(self):
        for values in [{'left': float('nan')}, {'right': 2}, {'left': .8, 'right': .2}]:
            with self.assertRaises(ValueError): validate_zone(values)

    def test_enter_held_exit_reenter_sends_two_events(self):
        session = Session()
        cd = ChangeDetection(['person'], 'http://localhost', 'test', 'test', session=session)
        with tempfile.TemporaryDirectory() as directory:
            for predictions in [[self.outside], [self.inside], [self.inside], [self.outside], [self.inside]]:
                current = [int(bool(eligible_detections(predictions, (100, 100, 3), self.zone)))]
                cd.add(['person'], current, directory, np.zeros((100, 100, 3), dtype=np.uint8), zone_name='현관')
        self.assertEqual(len(session.uploads), 2)
        self.assertEqual(session.uploads[0]['data']['zone_name'], '현관')

    def test_unavailable_initial_server_settings_does_not_silently_disable_roi(self):
        detector = type('Detector', (), {'token': None, 'authenticate': lambda self: (_ for _ in ()).throw(ConnectionError())})()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError): RemoteZone(detector, directory).get()

    def test_disabled_monitoring_excludes_all_objects_even_without_roi(self):
        zone=validate_zone({'monitoring_enabled':False,'zone_enabled':False})
        self.assertEqual(eligible_detections([self.inside],(100,100,3),zone),[])

    def test_off_never_flushes_pending_and_on_detects_held_person_again(self):
        session=Session();cd=ChangeDetection(['person'],'http://localhost','test','test',session=session)
        image=np.zeros((100,100,3),dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            session.failures=[503]
            self.assertEqual(cd.add(['person'],[1],directory,image),[])
            self.assertEqual(len(list((Path(directory)/'outbox').glob('*.json'))),1)
            session.failures=[503]
            cd.set_monitoring(False)
            self.assertEqual(cd.add(['person'],[1],directory,image),[])
            self.assertEqual(cd.flush(directory),[])
            self.assertEqual(session.failures,[503],'OFF must not attempt a pending upload')
            self.assertEqual(len(session.uploads),0)
            session.failures=[]
            cd.set_monitoring(True)
            self.assertEqual(len(cd.add(['person'],[1],directory,image)),2)
            self.assertEqual(len(session.uploads),2)

    def test_server_pause_quarantines_rejected_event_instead_of_retrying_on_resume(self):
        session=Session();session.failures=[423]
        cd=ChangeDetection(['person'],'http://localhost','test','test',session=session)
        image=np.zeros((100,100,3),dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(cd.add(['person'],[1],directory,image),[])
            self.assertTrue(cd.server_paused)
            self.assertEqual(len(list((Path(directory)/'paused').glob('*.json'))),1)
            self.assertEqual(list((Path(directory)/'outbox').glob('*.json')),[])
            cd.set_monitoring(True)
            self.assertEqual(len(cd.add(['person'],[1],directory,image)),1)
            self.assertEqual(len(session.uploads),1)
