"""
normalize.py — Shared contour normalization and geometric matching helpers.

The same preprocessing is applied to both country outlines and chapati contours so
that matching is based on shape geometry rather than raw image or coordinate-system
artifacts.
"""
from __future__ import annotations

import math
from typing import Literal

import cv2
import numpy as np


ScaleMethod = Literal["bounding_box_diagonal", "sqrt_area", "max_radius"]


def _to_float_points(contour: np.ndarray) -> np.ndarray:
    pts = np.asarray(contour, dtype=np.float32)
    if pts.ndim == 3 and pts.shape[1] == 1:
        pts = pts[:, 0, :]
    elif pts.ndim == 2 and pts.shape[-1] == 2:
        pass
    else:
        raise ValueError(f"Unsupported contour shape: {pts.shape}")

    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) < 3:
        raise ValueError("Contour must have at least 3 finite points.")
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    return pts


def _geometric_centroid(points: np.ndarray) -> np.ndarray:
    pts = _to_float_points(points)
    contour = pts.reshape(-1, 1, 2).astype(np.float32)
    moments = cv2.moments(contour)
    m00 = moments["m00"]
    if abs(m00) < 1e-9:
        return pts.mean(axis=0)
    return np.array([moments["m10"] / m00, moments["m01"] / m00], dtype=np.float32)


def _resample_closed_contour(points: np.ndarray, n_points: int = 256) -> np.ndarray:
    pts = _to_float_points(points)
    if len(pts) < 4:
        return pts.copy()

    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = float(seg.sum())
    if total <= 1e-9:
        return np.linspace(0, 1, n_points, endpoint=False).reshape(-1, 1) * np.array([0.0, 0.0])

    if n_points <= 0:
        raise ValueError("n_points must be positive")

    cumulative = np.concatenate(([0.0], np.cumsum(seg)))
    target = np.linspace(0.0, total, n_points, endpoint=False)
    out = []
    j = 0

    for d in target:
        while j + 1 < len(cumulative) and cumulative[j + 1] < d:
            j += 1
        if cumulative[j + 1] == cumulative[j]:
            out.append(pts[j])
            continue

        t = (d - cumulative[j]) / (cumulative[j + 1] - cumulative[j])
        point = pts[j] + t * (pts[j + 1] - pts[j])
        out.append(point)

    resampled = np.asarray(out, dtype=np.float32)
    return resampled


def normalize_contour(
    contour: np.ndarray,
    scale_method: ScaleMethod = "bounding_box_diagonal",
    n_points: int = 256,
) -> np.ndarray:
    """Center, resample, and scale a contour using a geometric centroid."""
    pts = _resample_closed_contour(contour, n_points=n_points)
    centroid = _geometric_centroid(pts)
    centered = pts - centroid

    scale = _compute_scale(centered, scale_method)
    if scale < 1e-9:
        raise ValueError(
            f"Computed scale is effectively zero ({scale}); the contour may be degenerate."
        )

    normalized = centered / scale
    return normalized.reshape(-1, 1, 2).astype(np.float32)


def _compute_scale(flat: np.ndarray, method: ScaleMethod) -> float:
    if method == "bounding_box_diagonal":
        x_min, y_min = flat.min(axis=0)
        x_max, y_max = flat.max(axis=0)
        return math.sqrt((x_max - x_min) ** 2 + (y_max - y_min) ** 2)

    if method == "sqrt_area":
        x = flat[:, 0]
        y = flat[:, 1]
        area = abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2.0
        return math.sqrt(area) if area > 0 else 1.0

    if method == "max_radius":
        radii = np.sqrt(flat[:, 0] ** 2 + flat[:, 1] ** 2)
        return float(radii.max())

    raise ValueError(f"Unknown scale_norm_method: '{method}'")


def rotate_contour(points: np.ndarray, angle_rad: float) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    rot = np.column_stack([pts[:, 0] * c - pts[:, 1] * s, pts[:, 0] * s + pts[:, 1] * c])
    return rot.astype(np.float32)


def contour_distance(a: np.ndarray, b: np.ndarray, n_points: int = 256) -> float:
    """Geometric boundary distance invariant to translation, scale, rotation, and reflection."""
    a_pts = normalize_contour(_to_float_points(a), n_points=n_points)
    b_pts = normalize_contour(_to_float_points(b), n_points=n_points)

    a_pts = a_pts.reshape(-1, 2)
    b_pts = b_pts.reshape(-1, 2)

    best = float("inf")
    for step in range(32):
        angle = (2.0 * math.pi * step) / 32.0
        a_rot = rotate_contour(a_pts, angle)
        b_rot = rotate_contour(b_pts, angle)
        best = min(best, float(np.mean(np.linalg.norm(a_rot - b_rot, axis=1))))

        b_reflected = np.column_stack([b_pts[:, 0], -b_pts[:, 1]])
        b_ref_rot = rotate_contour(b_reflected, angle)
        best = min(best, float(np.mean(np.linalg.norm(a_rot - b_ref_rot, axis=1))))

    return float(best)


def contour_to_list(contour: np.ndarray) -> list[list[float]]:
    flat = contour.reshape(-1, 2)
    return flat.tolist()


def list_to_contour(pts: list[list[float]]) -> np.ndarray:
    arr = np.array(pts, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[:, np.newaxis, :]
    return arr
