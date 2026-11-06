import sys
import unittest
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from detect import YoloV5


@unittest.skipUnless((ROOT / 'models/yolov5n.onnx').is_file(), 'Run download_assets.py to fetch the official model')
class RealInferenceTests(unittest.TestCase):
    def test_official_bus_image_detects_people_and_bus(self):
        image = cv2.imread(str(ROOT / 'data/bus.jpg'))
        self.assertIsNotNone(image)
        predictions = YoloV5(ROOT / 'models/yolov5n.onnx').infer(image)
        labels = [item['name'] for item in predictions]
        self.assertIn('person', labels)
        self.assertIn('bus', labels)
        height, width = image.shape[:2]
        for item in predictions:
            x1, y1, x2, y2 = item['xyxy']
            self.assertTrue(0 <= x1 < x2 <= width)
            self.assertTrue(0 <= y1 < y2 <= height)
            self.assertTrue(.4 <= item['confidence'] <= 1)


if __name__ == '__main__':
    unittest.main()
