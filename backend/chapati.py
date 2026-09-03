"""
chapati.py — Online per-request chapati image processing pipeline.

Stages:
  1. Decode uploaded image (JPEG, PNG, HEIC via pillow-heif if available)
  2. Grayscale → Gaussian blur → threshold (Otsu or adaptive)
  3. Morphological cleanup (open+close)
  4. findContours → pick largest external contour
  5. Optional approxPolyDP simplification
  6. Return raw contour + overlay image (base64 PNG)

All thresholds are read from config.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from config import Settings, load_settings
from normalize import normalize_contour, contour_to_list


@dataclass
class AnalysisResult:
    """Returned by analyze_image — contains everything for the confirm step."""
    detected_contour: list[list[float]]       # raw (un-normalized) contour points [[x,y], ...]
    overlay_image_b64: str                    # base64 PNG of chapati photo with contour overlaid
    image_width: int
    image_height: int
    contour_area_ratio: float                 # fraction of image area covered by contour
    multiple_candidates: bool                 # True if 2 large contours found (ambiguous)
    candidate_contours: list[list[list[float]]]  # top-2 raw contours if ambiguous


@dataclass
class ProcessingError:
    """Returned instead of AnalysisResult when something goes wrong."""
    code: str          # e.g. "NO_CONTOUR", "TOO_SMALL", "DECODE_FAILED"
    message: str       # User-facing message


def analyze_image(
    image_bytes: bytes,
    settings: Optional[Settings] = None,
) -> AnalysisResult | ProcessingError:
    """
    Full online pipeline: bytes → detected contour + overlay image.

    Parameters
    ----------
    image_bytes : bytes
        Raw image bytes (JPEG / PNG / HEIC).
    settings : Settings, optional
        Loaded config; defaults to module-level singleton.

    Returns
    -------
    AnalysisResult on success, ProcessingError on failure.
    """
    if settings is None:
        settings = load_settings()
    ipc = settings.image_processing

    # --- 1. Decode ---
    img_bgr = _decode_image(image_bytes)
    if img_bgr is None:
        return ProcessingError(
            code="DECODE_FAILED",
            message="Could not decode image. Please upload a JPEG or PNG.",
        )

    h, w = img_bgr.shape[:2]

    # --- 2. Grayscale → blur → threshold ---
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur_k = _ensure_odd(ipc.blur_kernel)
    blurred = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

    if ipc.threshold_method == "otsu":
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:  # adaptive_gaussian
        thresh = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11, 2,
        )

    # --- 3. Morphological cleanup ---
    morph_k = _ensure_odd(ipc.morph_kernel)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_k, morph_k))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    # --- 4. Find contours ---
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return ProcessingError(
            code="NO_CONTOUR",
            message=(
                "No outline detected. Try placing your chapati on a plain, "
                "high-contrast surface (dark chapati on light plate, or vice versa)."
            ),
        )

    # Sort by area descending
    contours_sorted = sorted(contours, key=cv2.contourArea, reverse=True)
    best = contours_sorted[0]
    best_area = cv2.contourArea(best)
    image_area = float(h * w)

    # --- 5. Minimum area check ---
    area_ratio = best_area / image_area
    if area_ratio < ipc.min_contour_area_ratio:
        return ProcessingError(
            code="TOO_SMALL",
            message=(
                f"Detected shape is too small ({area_ratio*100:.1f}% of image). "
                "Move the chapati closer or crop out background."
            ),
        )

    # --- 6. Check for ambiguous duplicate contours ---
    multiple_candidates = False
    candidate_contours_raw = []
    if len(contours_sorted) >= 2:
        second_area = cv2.contourArea(contours_sorted[1])
        ratio = second_area / best_area if best_area > 0 else 0
        if ratio >= (1.0 - ipc.ambiguous_area_margin):
            multiple_candidates = True
            candidate_contours_raw = [contours_sorted[0], contours_sorted[1]]

    # --- 7. Optional simplification (keep unsimplified for display) ---
    display_contour = best  # always used for overlay
    match_contour = best

    if ipc.simplify_epsilon_pct > 0:
        epsilon = (ipc.simplify_epsilon_pct / 100.0) * cv2.arcLength(best, True)
        match_contour = cv2.approxPolyDP(best, epsilon, True)

    # --- 8. Draw overlay ---
    overlay_img = img_bgr.copy()
    cv2.drawContours(overlay_img, [display_contour], -1, (0, 255, 100), 3)
    overlay_b64 = _bgr_to_b64(overlay_img)

    detected_pts = _contour_to_simple_list(match_contour)
    candidates_pts = [_contour_to_simple_list(c) for c in candidate_contours_raw]

    return AnalysisResult(
        detected_contour=detected_pts,
        overlay_image_b64=overlay_b64,
        image_width=w,
        image_height=h,
        contour_area_ratio=float(area_ratio),
        multiple_candidates=multiple_candidates,
        candidate_contours=candidates_pts,
    )


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _decode_image(image_bytes: bytes) -> np.ndarray | None:
    """Decode image bytes to BGR numpy array. Supports JPEG, PNG, HEIC."""
    # Try HEIC first (optional dependency)
    try:
        import pillow_heif  # type: ignore
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(pil_img, dtype=np.uint8)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return bgr
    except Exception:
        pass

    # Fallback: OpenCV direct decode
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return bgr  # may be None if both fail


def _bgr_to_b64(img_bgr: np.ndarray) -> str:
    """Encode a BGR image as a base64 PNG string."""
    success, buf = cv2.imencode(".png", img_bgr)
    if not success:
        raise RuntimeError("Failed to encode overlay image as PNG.")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _ensure_odd(n: int) -> int:
    """Gaussian/morph kernels must be odd and ≥ 1."""
    n = max(1, n)
    return n if n % 2 == 1 else n + 1


def _contour_to_simple_list(contour: np.ndarray) -> list[list[float]]:
    """Convert OpenCV contour (N, 1, 2) to [[x, y], ...] float list."""
    return contour.reshape(-1, 2).astype(float).tolist()
