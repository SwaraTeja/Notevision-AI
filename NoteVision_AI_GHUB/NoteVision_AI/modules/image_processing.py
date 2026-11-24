"""Computer Vision: OpenCV image pre-processing pipeline used before OCR.

Pipeline: resize -> grayscale -> denoise -> background normalisation -> contrast (CLAHE)
          -> deskew -> adaptive thresholding.
"""
from __future__ import annotations

import cv2
import numpy as np

MIN_SIDE, MAX_SIDE = 1600, 2600


def resize_for_ocr(img: np.ndarray) -> tuple[np.ndarray, str]:
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest < MIN_SIDE:
        scale, note = MIN_SIDE / longest, f"Upscaled x{MIN_SIDE / longest:.2f} (small image)"
        interp = cv2.INTER_CUBIC
    elif longest > MAX_SIDE:
        scale, note = MAX_SIDE / longest, f"Downscaled x{MAX_SIDE / longest:.2f} (large image)"
        interp = cv2.INTER_AREA
    else:
        return img, "Size kept (already suitable)"
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=interp), note


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def normalise_background(gray: np.ndarray) -> np.ndarray:
    """Divide by an estimate of the page background to remove shadows / uneven lighting."""
    bg = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 21)
    return cv2.divide(gray, bg, scale=255)


def estimate_skew(gray: np.ndarray, max_angle: float = 6.0, step: float = 0.5) -> float:
    """Projection-profile skew estimation: the angle that makes text rows sharpest."""
    small = cv2.resize(gray, (600, int(600 * gray.shape[0] / gray.shape[1])), interpolation=cv2.INTER_AREA)
    _, inv = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = inv.shape
    best_angle, best_score = 0.0, -1.0
    for a in np.arange(-max_angle, max_angle + step, step):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        rot = cv2.warpAffine(inv, m, (w, h), flags=cv2.INTER_NEAREST)
        score = float(np.var(rot.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = float(a), score
    return best_angle


def rotate(img: np.ndarray, angle: float, border: int = 255) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def preprocess(img_bgr: np.ndarray) -> dict:
    """Run the full pipeline. Returns the intermediate images and a log of applied steps."""
    steps: list[str] = []
    img, note = resize_for_ocr(img_bgr)
    steps.append(note)

    gray = to_gray(img)
    steps.append("Converted to grayscale")

    gray = cv2.fastNlMeansDenoising(gray, None, h=8, templateWindowSize=7, searchWindowSize=21)
    steps.append("Noise reduction (non-local means denoising)")

    gray = normalise_background(gray)
    steps.append("Background normalisation (removes shadows and uneven lighting)")

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    steps.append("Contrast enhancement (CLAHE)")

    angle = estimate_skew(enhanced)
    if abs(angle) >= 0.5:
        enhanced = rotate(enhanced, angle)
        steps.append(f"Deskewed by {angle:+.1f} degrees")
    else:
        steps.append("Deskew not needed")

    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 41, 15)
    binary = cv2.medianBlur(binary, 3)
    steps.append("Adaptive Gaussian thresholding (binarisation)")

    return {"enhanced": enhanced, "binary": binary, "steps": steps}
