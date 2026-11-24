"""OCR engine: Tesseract (via pytesseract) on pre-processed images, with confidence scoring."""
from __future__ import annotations

import math
import os
import platform
import shutil
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract

import config
from modules import image_processing

_WIN_DEFAULTS = [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]


def _locate_tesseract() -> None:
    env = os.environ.get("TESSERACT_CMD")
    if env:
        pytesseract.pytesseract.tesseract_cmd = env
    elif not shutil.which("tesseract") and platform.system() == "Windows":
        for p in _WIN_DEFAULTS:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break


_locate_tesseract()


def tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@dataclass
class OcrResult:
    text: str
    confidence: float
    variant: str
    words: int
    processed: np.ndarray | None = None
    steps: list[str] = field(default_factory=list)


def _run(image: np.ndarray, psm: int = 3) -> tuple[str, float, int]:
    data = pytesseract.image_to_data(image, lang=config.OCR_LANG, config=f"--oem 3 --psm {psm}",
                                     output_type=pytesseract.Output.DICT)
    lines: dict[tuple, list[str]] = {}
    confs: list[float] = []
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue
        conf = float(data["conf"][i])
        if conf >= 0:
            confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    out, prev_par = [], None
    for (block, par, _line), words in lines.items():
        if prev_par is not None and (block, par) != prev_par:
            out.append("")
        out.append(" ".join(words))
        prev_par = (block, par)
    return "\n".join(out).strip(), (sum(confs) / len(confs) if confs else 0.0), len(confs)


def ocr_image(img_bgr: np.ndarray) -> OcrResult:
    """Pre-process the image, OCR the candidate versions and keep the more reliable result."""
    pre = image_processing.preprocess(img_bgr)
    candidates = []
    for name in ("enhanced", "binary"):
        text, conf, n = _run(pre[name])
        candidates.append(OcrResult(text, conf, name, n, pre[name], pre["steps"]))
        if conf >= 88 and n >= 20:      # clean scan: no need to try the other variant
            break
    best = max(candidates, key=lambda r: r.confidence * math.log1p(r.words))
    return best


def confidence_label(conf: float | None) -> str:
    if conf is None:
        return "n/a"
    if conf >= 80:
        return "High"
    if conf >= 60:
        return "Medium"
    return "Low"
