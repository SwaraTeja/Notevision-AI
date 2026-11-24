import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from modules import image_processing, ocr_engine

LINES = ["Supervised learning uses labeled data.", "Clustering groups similar data points."]


def _page(angle=0.0):
    img = Image.new("RGB", (1200, 400), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    for i, t in enumerate(LINES):
        d.text((60, 60 + i * 80), t, fill="black", font=font)
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if angle:
        m = cv2.getRotationMatrix2D((600, 200), angle, 1)
        arr = cv2.warpAffine(arr, m, (1200, 400), borderValue=(255, 255, 255))
    return arr


class ImageTests(unittest.TestCase):
    def test_preprocess_returns_images_and_steps(self):
        out = image_processing.preprocess(_page())
        self.assertEqual(out["enhanced"].ndim, 2)
        self.assertEqual(out["binary"].ndim, 2)
        self.assertTrue(any("grayscale" in s.lower() for s in out["steps"]))

    def test_deskew_detects_rotation(self):
        gray = cv2.cvtColor(_page(3), cv2.COLOR_BGR2GRAY)
        self.assertGreaterEqual(abs(image_processing.estimate_skew(gray)), 1.0)


@unittest.skipUnless(ocr_engine.tesseract_available(), "Tesseract not installed")
class OCRTests(unittest.TestCase):
    def test_ocr_reads_text(self):
        for angle in (0, 3):
            res = ocr_engine.ocr_image(_page(angle))
            self.assertIn("supervised", res.text.lower())
            self.assertIn("clustering", res.text.lower())
            self.assertGreater(res.confidence, 60)


if __name__ == "__main__":
    unittest.main()
