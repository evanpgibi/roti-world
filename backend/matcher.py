"""
matcher.py — Shape comparison engine.

Loads the country cache and exposes match_chapati():
  • Normalizes the chapati contour
  • Runs cv2.matchShapes against every cached country
  • Converts distances to similarity scores
  • Returns top-1 + leaderboard

All algorithm parameters are read from config.
"""
from __future__ import annotations

import math
import pickle
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import Settings, load_settings
from normalize import normalize_contour, list_to_contour, contour_to_list


# -------------------------------------------------------------------
# Result types
# -------------------------------------------------------------------
@dataclass
class CountryMatch:
    country: str
    iso_a3: str
    score: float        # 0–100
    distance: float     # raw matchShapes distance (lower = better)


@dataclass
class MatchResult:
    best_match: CountryMatch
    leaderboard: list[CountryMatch]          # top-N including best
    chapati_outline_normalized: list[list[float]]
    country_outline_normalized: list[list[float]]
    playful_copy: str


@dataclass
class MatchError:
    code: str
    message: str


# -------------------------------------------------------------------
# Cache loader (singleton per process)
# -------------------------------------------------------------------
_cache_payload: dict | None = None
_cache_loaded_from: str | None = None


def get_country_cache(settings: Settings) -> list[dict]:
    """
    Load and return the country cache (lazy, cached in module globals).
    Raises RuntimeError if the cache hasn't been built yet.
    """
    global _cache_payload, _cache_loaded_from

    cache_path = str(settings.resolve(settings.country_data.cache_path))

    if _cache_payload is None or _cache_loaded_from != cache_path:
        p = Path(cache_path)
        if not p.exists():
            raise RuntimeError(
                f"Country cache not found at '{cache_path}'.\n"
                "Run:  python backend/build_country_cache.py\n"
                "to build it first."
            )
        with open(p, "rb") as f:
            _cache_payload = pickle.load(f)
        _cache_loaded_from = cache_path

    return _cache_payload["countries"]  # type: ignore[index]


def invalidate_cache() -> None:
    """Force reload on next access (call after rebuilding the cache)."""
    global _cache_payload, _cache_loaded_from
    _cache_payload = None
    _cache_loaded_from = None


# -------------------------------------------------------------------
# Scoring helpers
# -------------------------------------------------------------------
_CV_METHODS = {
    "CONTOURS_MATCH_I1": cv2.CONTOURS_MATCH_I1,
    "CONTOURS_MATCH_I2": cv2.CONTOURS_MATCH_I2,
    "CONTOURS_MATCH_I3": cv2.CONTOURS_MATCH_I3,
}


def _distance_to_score(distance: float, formula: str, k: float) -> float:
    """
    Convert a matchShapes distance (0 = identical, unbounded above) to a
    human-friendly similarity percentage (0–100).
    """
    if formula == "exponential":
        return 100.0 * math.exp(-k * distance)
    elif formula == "linear_clamped":
        # 0 distance → 100%, distance ≥ 1/k → 0%
        return max(0.0, 100.0 * (1.0 - k * distance))
    else:
        raise ValueError(f"Unknown score_formula: '{formula}'")


# -------------------------------------------------------------------
# Copy template loader
# -------------------------------------------------------------------
def _load_copy_templates(templates_path: Path) -> list[dict]:
    import json
    if not templates_path.exists():
        return []
    with open(templates_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("buckets", [])


def _pick_copy(score: float, country: str, templates_path: Path) -> str:
    buckets = _load_copy_templates(templates_path)
    for bucket in buckets:
        if bucket["min"] <= score <= bucket["max"]:
            msgs = bucket.get("messages", [])
            if msgs:
                template = random.choice(msgs)
                return template.format(
                    country=country,
                    score=f"{score:.1f}",
                )
    return f"Your chapati is {score:.1f}% {country}."


# -------------------------------------------------------------------
# Core matching function
# -------------------------------------------------------------------
def match_chapati(
    contour_raw_pts: list[list[float]],
    settings: Optional[Settings] = None,
) -> MatchResult | MatchError:
    """
    Compare a chapati contour (from the /api/analyze confirm step) against
    every cached country contour and return the best match + leaderboard.

    Parameters
    ----------
    contour_raw_pts : list[[x, y]]
        Raw contour points as returned by analyze_image (un-normalized).
    settings : Settings, optional
        Loaded config.

    Returns
    -------
    MatchResult on success, MatchError on failure.
    """
    if settings is None:
        settings = load_settings()

    mc = settings.matching
    nm = settings.normalization

    # --- Load cache ---
    try:
        countries = get_country_cache(settings)
    except RuntimeError as e:
        return MatchError(code="CACHE_MISSING", message=str(e))

    if not countries:
        return MatchError(code="CACHE_EMPTY", message="Country cache is empty. Rebuild the cache.")

    # --- Normalize chapati contour ---
    try:
        raw = np.array(contour_raw_pts, dtype=np.float32).reshape(-1, 1, 2)
        chapati_norm = normalize_contour(raw, nm.scale_norm_method)
    except Exception as e:
        return MatchError(
            code="NORMALIZATION_FAILED",
            message=f"Failed to normalize chapati contour: {e}",
        )

    # --- Resolve matchShapes method ---
    cv_method = _CV_METHODS.get(mc.primary_method, cv2.CONTOURS_MATCH_I1)
    formula = mc.score_formula
    k = mc.score_k

    # --- Compare against every country ---
    results: list[tuple[float, dict]] = []  # (distance, country_entry)

    for entry in countries:
        try:
            country_contour = list_to_contour(entry["contour_points"])
            dist = cv2.matchShapes(chapati_norm, country_contour, cv_method, 0.0)
            results.append((dist, entry))
        except Exception:
            continue  # skip degenerate entries silently

    if not results:
        return MatchError(
            code="NO_RESULTS",
            message="Shape comparison failed for all countries. Check the cache.",
        )

    # --- Sort ascending by distance (best match first) ---
    results.sort(key=lambda t: t[0])

    leaderboard_size = min(mc.leaderboard_size, len(results))
    top_results = results[:leaderboard_size]

    leaderboard: list[CountryMatch] = []
    for dist, entry in top_results:
        score = _distance_to_score(dist, formula, k)
        leaderboard.append(
            CountryMatch(
                country=entry["name"],
                iso_a3=entry["iso_a3"],
                score=round(score, 1),
                distance=round(dist, 6),
            )
        )

    best = leaderboard[0]
    best_entry = top_results[0][1]
    country_norm = list_to_contour(best_entry["contour_points"])

    # --- Pick copy template ---
    copy_path = settings.resolve(settings.copy.templates_path)
    playful_copy = _pick_copy(best.score, best.country, copy_path)

    return MatchResult(
        best_match=best,
        leaderboard=leaderboard,
        chapati_outline_normalized=contour_to_list(chapati_norm),
        country_outline_normalized=contour_to_list(country_norm),
        playful_copy=playful_copy,
    )
