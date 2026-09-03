"""
main.py — RotiWorld FastAPI backend.

Endpoints:
  POST /api/analyze   — Upload chapati photo → detected outline + overlay
  POST /api/match     — Confirmed contour → best country match + leaderboard
  GET  /api/share     — Generate shareable PNG card
  GET  /api/cache/info — Cache metadata (build time, count, etc.)
  POST /api/cache/rebuild — Trigger cache rebuild (admin use)
  GET  /api/health    — Health check

Run with:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import base64
import traceback
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from chapati import analyze_image, AnalysisResult, ProcessingError
from config import load_settings
from matcher import get_country_cache, invalidate_cache, match_chapati, MatchResult, MatchError
from share import generate_share_card

# -------------------------------------------------------------------
# App setup
# -------------------------------------------------------------------
app = FastAPI(
    title="RotiWorld API",
    description=(
        "A deliberately useless computer-vision toy: "
        "photograph a misshapen chapati, and the app tells you — with "
        "unwarranted confidence — which country it most closely resembles."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = load_settings()

# -------------------------------------------------------------------
# Request / Response models
# -------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    detected_contour: list[list[float]] = Field(
        description="Raw (un-normalized) contour points [[x, y], ...]"
    )
    overlay_image_b64: str = Field(
        description="Base64 PNG: original photo with detected outline overlaid"
    )
    image_width: int
    image_height: int
    contour_area_ratio: float
    multiple_candidates: bool = Field(
        description="True if two large contours found — user should confirm which one"
    )
    candidate_contours: list[list[list[float]]] = Field(
        default=[],
        description="Top-2 raw contours if multiple_candidates is True",
    )
    confirm_required: bool = True


class AnalyzeError(BaseModel):
    error: bool = True
    code: str
    message: str


class CountryMatchModel(BaseModel):
    country: str
    iso_a3: str
    score: float
    distance: float


class MatchRequest(BaseModel):
    contour: list[list[float]] = Field(
        description="Confirmed contour points [[x, y], ...] from /api/analyze"
    )


class MatchResponse(BaseModel):
    best_match: CountryMatchModel
    leaderboard: list[CountryMatchModel]
    chapati_outline_normalized: list[list[float]]
    country_outline_normalized: list[list[float]]
    playful_copy: str


class ShareRequest(BaseModel):
    best_country: str
    best_iso: str
    best_score: float
    leaderboard: list[dict]
    chapati_outline: list[list[float]]
    country_outline: list[list[float]]
    playful_copy: str


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Health check — returns OK and whether the cache is loaded."""
    cache_ready = False
    n_countries = 0
    try:
        countries = get_country_cache(settings)
        cache_ready = True
        n_countries = len(countries)
    except Exception:
        pass
    return {"status": "ok", "cache_ready": cache_ready, "n_countries": n_countries}


@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
    responses={400: {"model": AnalyzeError}, 413: {"model": AnalyzeError}},
    summary="Upload chapati photo → detected outline",
)
async def analyze(image: UploadFile = File(..., description="Chapati photo (JPEG/PNG/HEIC)")):
    """
    Stage 1: Upload photo → contour detection + overlay image.

    The client should display the overlay image and ask the user to confirm.
    Then pass `detected_contour` to POST /api/match.
    """
    # Size check
    max_bytes = settings.image_processing.max_upload_mb * 1024 * 1024
    image_bytes = await image.read()

    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "error": True,
                "code": "FILE_TOO_LARGE",
                "message": (
                    f"Image exceeds {settings.image_processing.max_upload_mb} MB limit. "
                    "Please compress or crop your photo."
                ),
            },
        )

    result = analyze_image(image_bytes, settings)

    if isinstance(result, ProcessingError):
        raise HTTPException(
            status_code=400,
            detail={"error": True, "code": result.code, "message": result.message},
        )

    return AnalyzeResponse(
        detected_contour=result.detected_contour,
        overlay_image_b64=result.overlay_image_b64,
        image_width=result.image_width,
        image_height=result.image_height,
        contour_area_ratio=result.contour_area_ratio,
        multiple_candidates=result.multiple_candidates,
        candidate_contours=result.candidate_contours,
        confirm_required=True,
    )


@app.post(
    "/api/match",
    response_model=MatchResponse,
    responses={400: {"model": AnalyzeError}, 503: {"model": AnalyzeError}},
    summary="Confirmed contour → country match + leaderboard",
)
async def match(req: MatchRequest):
    """
    Stage 2: Pass the confirmed chapati contour → get best country match.

    The `contour` field should be `detected_contour` from /api/analyze
    (the user has confirmed the outline looks correct).
    """
    if len(req.contour) < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "error": True,
                "code": "INVALID_CONTOUR",
                "message": "Contour must have at least 3 points.",
            },
        )

    result = match_chapati(req.contour, settings)

    if isinstance(result, MatchError):
        status = 503 if result.code == "CACHE_MISSING" else 400
        raise HTTPException(
            status_code=status,
            detail={"error": True, "code": result.code, "message": result.message},
        )

    return MatchResponse(
        best_match=CountryMatchModel(
            country=result.best_match.country,
            iso_a3=result.best_match.iso_a3,
            score=result.best_match.score,
            distance=result.best_match.distance,
        ),
        leaderboard=[
            CountryMatchModel(
                country=m.country,
                iso_a3=m.iso_a3,
                score=m.score,
                distance=m.distance,
            )
            for m in result.leaderboard
        ],
        chapati_outline_normalized=result.chapati_outline_normalized,
        country_outline_normalized=result.country_outline_normalized,
        playful_copy=result.playful_copy,
    )


@app.post(
    "/api/share",
    summary="Generate shareable PNG card",
    response_class=Response,
)
async def share_card(req: ShareRequest):
    """
    Generate a branded shareable PNG card with outlines, score, and leaderboard.
    Returns raw PNG bytes (Content-Type: image/png).
    """
    try:
        png_bytes = generate_share_card(
            best_country=req.best_country,
            best_iso=req.best_iso,
            best_score=req.best_score,
            leaderboard=req.leaderboard,
            chapati_outline=req.chapati_outline,
            country_outline=req.country_outline,
            playful_copy=req.playful_copy,
        )
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache/info", summary="Country cache metadata")
async def cache_info():
    """Return metadata about the loaded country cache (build time, source, count)."""
    from pathlib import Path
    import pickle

    cache_path = settings.resolve(settings.country_data.cache_path)
    if not cache_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Cache not found. Run: python backend/build_country_cache.py",
        )
    with open(cache_path, "rb") as f:
        payload = pickle.load(f)
    return payload.get("metadata", {})


@app.post("/api/cache/rebuild", summary="Rebuild country cache (admin)")
async def rebuild_cache():
    """
    Trigger an in-process cache rebuild.
    ⚠️ Blocks the process for a few seconds while parsing GeoJSON.
    """
    import asyncio
    from build_country_cache import build_cache

    try:
        await asyncio.get_event_loop().run_in_executor(None, build_cache)
        invalidate_cache()
        return {"status": "ok", "message": "Cache rebuilt successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------------------
# Dev entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
