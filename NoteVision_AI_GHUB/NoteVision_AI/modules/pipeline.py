"""Upload pipeline: validate -> store -> (PDF to images / embedded text) -> OCR -> save to database."""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pymupdf

import config
from database.db_manager import Database
from modules import ocr_engine, ppt_reader

Progress = Callable[[float, str], None]
LOW_CONFIDENCE = 60.0


class ProcessingError(Exception):
    """Raised with a message that is safe and useful to show to the student."""


def safe_filename(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._") or "notes"
    return stem[:60] + Path(name).suffix.lower()


def validate(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise ProcessingError(f"'{ext or filename}' is not supported. Upload a JPG, JPEG, PNG, PDF or PowerPoint (PPTX) file.")
    if not data:
        raise ProcessingError("The file is empty. Choose a different file.")
    if len(data) > config.MAX_FILE_MB * 1024 * 1024:
        raise ProcessingError(f"The file is larger than {config.MAX_FILE_MB} MB. Compress it or split it into smaller parts.")
    return ext


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ProcessingError("The image could not be read. The file may be corrupted or not a real image.")
    return img


def open_pdf(data: bytes):
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ProcessingError("The PDF could not be opened. The file may be corrupted.")
    if doc.needs_pass:
        raise ProcessingError("This PDF is password protected. Remove the password and upload it again.")
    if doc.page_count == 0:
        raise ProcessingError("The PDF has no pages.")
    if doc.page_count > config.MAX_PDF_PAGES:
        raise ProcessingError(f"The PDF has {doc.page_count} pages. The limit is {config.MAX_PDF_PAGES}; split it first.")
    return doc


def render_pdf_page(page, dpi: int = config.PDF_RENDER_DPI) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def pdf_first_page_png(data: bytes) -> bytes | None:
    """Preview helper for the upload screen."""
    try:
        doc = open_pdf(data)
        ok, buf = cv2.imencode(".png", render_pdf_page(doc[0], dpi=80))
        return buf.tobytes() if ok else None
    except ProcessingError:
        return None


def _preview(img: np.ndarray, width: int = 1100) -> bytes:
    h, w = img.shape[:2]
    if w > width:
        img = cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _read_presentation(data: bytes, ext: str, say: Progress) -> tuple[list[dict], list]:
    """One 'page' per slide: title + body text + tables + speaker notes. Pictures on text-poor slides are OCR-ed."""
    try:
        if ext == ".ppt":
            say(0.08, "Converting old .ppt to .pptx…")
            data = ppt_reader.convert_ppt_to_pptx(data)
        prs = ppt_reader.open_presentation(data, config.MAX_SLIDES)
        slides = ppt_reader.extract_slides(prs)
    except ppt_reader.PptError as e:
        raise ProcessingError(str(e))
    can_ocr = ocr_engine.tesseract_available()
    pages, previews, total = [], [], len(slides)
    for i, sl in enumerate(slides):
        say(0.1 + 0.8 * i / total, f"Reading slide {i + 1} of {total}…")
        parts, method, conf = [], "Slide text", 100.0
        body = sl["text"]
        if sl["title"] and not body.startswith(sl["title"]):
            body = f"{sl['title']}\n{body}".strip()
        if body:
            parts.append(body)
        if len(body) < config.MIN_SLIDE_TEXT_CHARS and can_ocr and sl["pictures"]:   # slide is mostly images
            ocr_texts, ocr_confs = [], []
            for blob in sl["pictures"][:4]:
                try:
                    res = ocr_engine.ocr_image(decode_image(blob))
                except ProcessingError:
                    continue
                if res.text.strip():
                    ocr_texts.append(res.text.strip()); ocr_confs.append(res.confidence)
            if ocr_texts:
                parts.append("\n".join(ocr_texts))
                method = "Slide text + picture OCR" if body else "Picture OCR (slide images)"
                conf = round(sum(ocr_confs) / len(ocr_confs), 1) if not body else 100.0
        if sl["notes"]:
            parts.append("Speaker notes: " + sl["notes"])
        pages.append({"page_no": sl["slide_no"], "text": "\n\n".join(parts), "method": method,
                      "confidence": conf if parts else None})
        previews.append(None)
    return pages, previews


def process_upload(db: Database, data: bytes, filename: str, title: str, subject: str,
                   progress: Progress | None = None) -> dict:
    """Run the whole pipeline. Returns {'doc_id','pages','confidence','status'}."""
    say = progress or (lambda f, m: None)
    ext = validate(filename, data)
    if ext not in (".pptx", ".ppt") and not ocr_engine.tesseract_available():
        raise ProcessingError("Tesseract OCR is not installed or not on PATH. See the README for installation steps.")

    say(0.05, "Validating file…")
    stored = config.UPLOAD_DIR / f"{uuid.uuid4().hex[:12]}_{safe_filename(filename)}"
    pages: list[dict] = []
    previews: list[tuple[bytes, bytes | None]] = []

    if ext == ".pdf":
        pdf = open_pdf(data)
        total = pdf.page_count
        for i, page in enumerate(pdf):
            say(0.1 + 0.8 * i / total, f"Reading page {i + 1} of {total}…")
            embedded = page.get_text("text").strip()
            img = render_pdf_page(page)
            if len(embedded) >= 40:                       # digital PDF: use the real text, no OCR errors
                pages.append({"page_no": i + 1, "text": embedded, "method": "Embedded PDF text", "confidence": 100.0})
                previews.append((_preview(img), None))
            else:                                         # scanned PDF page: OCR it
                res = ocr_engine.ocr_image(img)
                pages.append({"page_no": i + 1, "text": res.text, "method": f"OCR ({res.variant})",
                              "confidence": round(res.confidence, 1)})
                previews.append((_preview(img), _preview(res.processed)))
        file_type = "pdf"
    elif ext in (".pptx", ".ppt"):
        pages, previews = _read_presentation(data, ext, say)
        file_type = "pptx"
    else:
        say(0.2, "Pre-processing image (grayscale, denoise, threshold)…")
        img = decode_image(data)
        say(0.5, "Running OCR…")
        res = ocr_engine.ocr_image(img)
        pages.append({"page_no": 1, "text": res.text, "method": f"OCR ({res.variant})",
                      "confidence": round(res.confidence, 1)})
        previews.append((_preview(img), _preview(res.processed)))
        file_type = ext.lstrip(".")

    if not any(p["text"].strip() for p in pages):
        raise ProcessingError("No readable text was found. Try a sharper, well-lit photo with the page filling the frame, "
                              "or type the notes manually in the Notes Analyzer after uploading a clearer scan.")

    say(0.92, "Saving to your library…")
    stored.write_bytes(data)
    confs = [p["confidence"] for p in pages if p["confidence"] is not None]
    avg = round(sum(confs) / len(confs), 1) if confs else None
    status = "Needs review" if (avg is not None and avg < LOW_CONFIDENCE) else "Ready"
    try:
        doc_id = db.add_document(title.strip() or Path(filename).stem, subject, filename, str(stored), file_type,
                                 len(pages), status, avg)
        db.add_pages(doc_id, pages)
        out_dir = config.GENERATED_DIR / f"doc_{doc_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        for n, pv in enumerate(previews, 1):
            if pv is None:
                continue
            orig, proc = pv
            (out_dir / f"page_{n}_original.png").write_bytes(orig)
            if proc:
                (out_dir / f"page_{n}_processed.png").write_bytes(proc)
        db.log_activity("upload", doc_id, f"Uploaded {filename}")
    except Exception:
        stored.unlink(missing_ok=True)
        raise
    say(1.0, "Done")
    return {"doc_id": doc_id, "pages": len(pages), "confidence": avg, "status": status}


def create_text_document(db: Database, title: str, subject: str, text: str, demo: bool = False) -> int:
    """Store notes typed/pasted by the student (or the labelled demo notes) without OCR."""
    if len(text.split()) < 10:
        raise ProcessingError("Add at least a few sentences of notes.")
    doc_id = db.add_document(title, subject, None, None, "text", 1, "Ready", None, demo)
    db.add_pages(doc_id, [{"page_no": 1, "text": text.strip(), "method": "Typed / demo text", "confidence": None}])
    db.log_activity("upload", doc_id, "Added typed notes" if not demo else "Loaded demo notes")
    return doc_id


def delete_document_files(doc_id: int, stored_path: str | None) -> None:
    if stored_path:
        Path(stored_path).unlink(missing_ok=True)
    shutil.rmtree(config.GENERATED_DIR / f"doc_{doc_id}", ignore_errors=True)
