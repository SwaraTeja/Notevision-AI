"""Read PowerPoint files (.pptx, and legacy .ppt via LibreOffice) into per-slide text."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.exc import PackageNotFoundError


class PptError(Exception):
    """Message is safe to show to the student."""


def convert_ppt_to_pptx(data: bytes) -> bytes:
    """Legacy .ppt -> .pptx using LibreOffice (only if it is installed)."""
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise PptError("Old .ppt files need LibreOffice to be converted. Save the file as .pptx in PowerPoint "
                       "and upload that instead.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.ppt"
        src.write_bytes(data)
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pptx", "--outdir", tmp, str(src)],
                           check=True, capture_output=True, timeout=120)
        except Exception:
            raise PptError("The .ppt file could not be converted. Save it as .pptx in PowerPoint and upload that.")
        out = Path(tmp) / "in.pptx"
        if not out.exists():
            raise PptError("The .ppt file could not be converted. Save it as .pptx in PowerPoint and upload that.")
        return out.read_bytes()


def open_presentation(data: bytes, max_slides: int):
    try:
        prs = Presentation(io.BytesIO(data))
    except (PackageNotFoundError, KeyError, ValueError, Exception):
        raise PptError("The presentation could not be opened. The file may be corrupted or password protected.")
    n = len(prs.slides)
    if n == 0:
        raise PptError("The presentation has no slides.")
    if n > max_slides:
        raise PptError(f"The presentation has {n} slides. The limit is {max_slides}; split it first.")
    return prs


def _shape_items(shape, texts: list[str], pictures: list[bytes]) -> None:
    """Collect text (in reading order) and picture bytes from a shape, recursing into groups."""
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for sub in shape.shapes:
            _shape_items(sub, texts, pictures)
        return
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        try:
            pictures.append(shape.image.blob)
        except Exception:
            pass
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells if c.text.strip()]
            if cells:
                texts.append(" | ".join(cells))
    elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            line = "".join(r.text for r in para.runs).strip()
            if line:
                texts.append(line)


def extract_slides(prs) -> list[dict]:
    """Return [{'slide_no', 'title', 'text', 'notes', 'pictures'}] for each slide."""
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        title = ""
        try:
            if slide.shapes.title is not None:
                title = slide.shapes.title.text.strip()
        except Exception:
            pass
        texts: list[str] = []
        pictures: list[bytes] = []
        ordered = sorted(slide.shapes, key=lambda s: (s.top or 0, s.left or 0))
        for shape in ordered:
            _shape_items(shape, texts, pictures)
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        slides.append({"slide_no": i, "title": title, "text": "\n".join(texts), "notes": notes, "pictures": pictures})
    return slides


def first_slides_outline(data: bytes, ext: str, limit: int = 5) -> list[tuple[int, str]] | None:
    """Preview helper for the upload screen: (slide number, first line of text)."""
    try:
        if ext == ".ppt":
            return None
        prs = open_presentation(data, 10_000)
        out = []
        for s in extract_slides(prs)[:limit]:
            line = s["title"] or (s["text"].splitlines()[0] if s["text"] else "(no text)")
            out.append((s["slide_no"], line))
        return out
    except PptError:
        return None
