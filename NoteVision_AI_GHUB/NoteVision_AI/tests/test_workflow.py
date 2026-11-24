"""End-to-end test of the upload pipeline (image, digital PDF, scanned PDF, bad files)."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

import config
from database.db_manager import Database
from modules import ocr_engine, pipeline


def _png() -> bytes:
    img = Image.new("RGB", (1200, 300), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError:
        f = ImageFont.load_default()
    d.text((60, 60), "Clustering is an example of unsupervised learning.", fill="black", font=f)
    d.text((60, 140), "Regression predicts a continuous number.", fill="black", font=f)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))
    return buf.tobytes()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "up").mkdir(); (root / "gen").mkdir()
        self._old = (config.UPLOAD_DIR, config.GENERATED_DIR)
        config.UPLOAD_DIR, config.GENERATED_DIR = root / "up", root / "gen"
        self.db = Database(root / "w.db")

    def tearDown(self):
        config.UPLOAD_DIR, config.GENERATED_DIR = self._old
        self.tmp.cleanup()

    @unittest.skipUnless(ocr_engine.tesseract_available(), "Tesseract not installed")
    def test_image_upload(self):
        r = pipeline.process_upload(self.db, _png(), "my notes (1).png", "T", "General")
        self.assertIn("clustering", self.db.get_full_text(r["doc_id"]).lower())
        self.assertEqual(self.db.get_document(r["doc_id"])["status"], "Ready")

    def test_pptx_upload(self):
        import io
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        s1 = prs.slides.add_slide(prs.slide_layouts[1])
        s1.shapes.title.text = "Supervised Learning"
        s1.placeholders[1].text = "Classification predicts a category. Regression predicts a number."
        s1.notes_slide.notes_text_frame.text = "Mention labelled data."
        s2 = prs.slides.add_slide(prs.slide_layouts[5])
        s2.shapes.title.text = "Comparison"
        tbl = s2.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(6), Inches(1)).table
        tbl.cell(0, 0).text = "Type"; tbl.cell(0, 1).text = "Output"
        tbl.cell(1, 0).text = "Clustering"; tbl.cell(1, 1).text = "Groups"
        buf = io.BytesIO(); prs.save(buf)
        r = pipeline.process_upload(self.db, buf.getvalue(), "deck.pptx", "Deck", "General")
        self.assertEqual(r["pages"], 2)
        doc = self.db.get_document(r["doc_id"])
        self.assertEqual(doc["file_type"], "pptx")
        text = self.db.get_full_text(r["doc_id"])
        for needle in ("Supervised Learning", "Regression predicts a number", "Mention labelled data", "Clustering | Groups"):
            self.assertIn(needle, text)

    def test_corrupt_pptx(self):
        with self.assertRaises(pipeline.ProcessingError):
            pipeline.process_upload(self.db, b"not a pptx", "bad.pptx", "B", "General")

    @unittest.skipUnless(ocr_engine.tesseract_available(), "Tesseract not installed")
    def test_digital_and_scanned_pdf(self):
        d = pymupdf.open()
        d.new_page().insert_text((72, 72), "Overfitting occurs when a model memorizes the training data and fails on new data.")
        r = pipeline.process_upload(self.db, d.tobytes(), "a.pdf", "P", "General")
        self.assertEqual(self.db.get_pages(r["doc_id"])[0]["method"], "Embedded PDF text")
        s = pymupdf.open()
        p = s.new_page(width=600, height=150)
        p.insert_image(p.rect, stream=_png())
        r2 = pipeline.process_upload(self.db, s.tobytes(), "scan.pdf", "S", "General")
        self.assertTrue(self.db.get_pages(r2["doc_id"])[0]["method"].startswith("OCR"))

    @unittest.skipUnless(ocr_engine.tesseract_available(), "Tesseract not installed")
    def test_bad_files_raise_friendly_errors(self):
        for name, data in [("a.txt", b"hi"), ("a.pdf", b"junk"), ("a.png", b""), ("a.png", b"junk")]:
            with self.subTest(name=name, size=len(data)):
                with self.assertRaises(pipeline.ProcessingError):
                    pipeline.process_upload(self.db, data, name, "x", "General")
                self.assertEqual(self.db.list_documents(), [])

    def test_safe_filename(self):
        self.assertEqual(pipeline.safe_filename("../../etc/pass wd?.PNG"), "pass_wd.png")


if __name__ == "__main__":
    unittest.main()
