"""
normalize.py — Scale-invariant contour normalization.

Applied identically to:
  • Every country contour (offline, at cache-build time)
  • The chapati contour (online, per request)

This ensures the comparison engine only sees shape, never size or position.
"""
from __future__ import annotations

import math
from typing import Literal

import cv2
import numpy as np


ScaleMethod = Literal["bounding_box_diagonal", "sqrt_area", "max_radius"]


def normalize_contour(
    contour: np.ndarray,
    scale_method: ScaleMethod = "bounding_box_diagonal",
) -> np.ndarray:
    """
    Center and scale-normalize a contour.

    Parameters
    ----------
    contour : np.ndarray
        Shape (N, 1, 2) or (N, 2) — OpenCV-compatible contour points.
    scale_method : ScaleMethod
        Which measure to use for scale normalization.

    Returns
    -------
    np.ndarray
        Normalized contour, shape (N, 1, 2), dtype float32.
        Centroid is at (0, 0); scale is dimensionless.

    Raises
    ------
    ValueError
        If the contour has fewer than 3 points, or the computed scale is zero.
    """
    # Ensure float32 and shape (N, 1, 2)
    pts = contour.astype(np.float32)
    if pts.ndim == 2:
        pts = pts[:, np.newaxis, :]  # (N, 2) → (N, 1, 2)

    n = pts.shape[0]
    if n < 3:
        raise ValueError(f"Contour must have at least 3 points, got {n}.")

    # --- Translation invariance: center at centroid ---
    flat = pts.reshape(-1, 2)  # (N, 2)
    cx, cy = float(flat[:, 0].mean()), float(flat[:, 1].mean())
    flat = flat - np.array([cx, cy], dtype=np.float32)

    # --- Scale normalization ---
    scale = _compute_scale(flat, scale_method)
    if scale < 1e-9:
        raise ValueError(
            f"Computed scale is effectively zero ({scale}); "
            "the contour may be degenerate."
        )

    flat = flat / scale

    return flat.reshape(-1, 1, 2).astype(np.float32)


def _compute_scale(flat: np.ndarray, method: ScaleMethod) -> float:
    """Compute a scale denominator from centered (zero-mean) points."""
    if method == "bounding_box_diagonal":
        x_min, y_min = flat.min(axis=0)
        x_max, y_max = flat.max(axis=0)
        return math.sqrt((x_max - x_min) ** 2 + (y_max - y_min) ** 2)

    elif method == "sqrt_area":
        # Shoelace formula for polygon area
        x = flat[:, 0]
        y = flat[:, 1]
        area = abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2.0
        return math.sqrt(area) if area > 0 else 1.0

    elif method == "max_radius":
        radii = np.sqrt(flat[:, 0] ** 2 + flat[:, 1] ** 2)
        return float(radii.max())

    else:
        raise ValueError(f"Unknown scale_norm_method: '{method}'")


def contour_to_list(contour: np.ndarray) -> list[list[float]]:
    """Convert an (N, 1, 2) float32 contour to a JSON-serializable list."""
    flat = contour.reshape(-1, 2)
    return flat.tolist()


def list_to_contour(pts: list[list[float]]) -> np.ndarray:
    """Convert a JSON list back to an (N, 1, 2) float32 contour."""
    arr = np.array(pts, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[:, np.newaxis, :]
    return arr
