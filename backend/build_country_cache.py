"""
build_country_cache.py — Offline pipeline: parse country boundaries → normalize → cache.

Run once (or on config change):
    python build_country_cache.py

Supports two data sources (configured in config.yaml):
  • geojson  — parses WRI all_primary_countries.geojson with geopandas/shapely
  • svg      — parses WRI intl_wintri.svg (whole-world SVG, paths split by group)

Output: country_cache.pkl — a list of CountryEntry dicts, plus provenance metadata.
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import time
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np

# -------------------------------------------------------------------
# Resolve project root so this script can be run from anywhere
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import load_settings
from normalize import normalize_contour, contour_to_list


# -------------------------------------------------------------------
# Types
# -------------------------------------------------------------------
class CountryEntry(TypedDict):
    iso_a3: str
    name: str
    contour_points: list[list[float]]   # normalized, JSON-serializable
    hu_moments: list[float]             # 7 Hu moments from the normalized contour
    raw_area: float                     # area before normalization (pixel² in SVG, m² in GeoJSON)
    raw_bbox: list[float]               # [x_min, y_min, x_max, y_max] before normalization


class CacheMetadata(TypedDict):
    built_at: str
    source: str
    source_path: str
    polygon_strategy: str
    scale_norm_method: str
    n_countries: int
    attribution: str


# -------------------------------------------------------------------
# GeoJSON pipeline
# -------------------------------------------------------------------
def _load_geojson(geojson_path: Path, strategy: str, scale_method: str) -> list[CountryEntry]:
    """Parse GeoJSON → per-country normalized contours."""
    try:
        import geopandas as gpd
        from shapely.geometry import MultiPolygon, Polygon
    except ImportError as e:
        raise SystemExit(
            "geopandas / shapely not installed. Run: pip install geopandas shapely"
        ) from e

    print(f"[GeoJSON] Loading {geojson_path} ...")
    gdf = gpd.read_file(str(geojson_path))
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.to_crs("EPSG:3857")
    print(f"[GeoJSON] Loaded {len(gdf)} features. Columns: {list(gdf.columns)}")

    entries: list[CountryEntry] = []
    skipped = 0

    # Detect name/ISO columns (WRI uses different field names across versions)
    name_col = _detect_col(gdf.columns, ["NAME", "name", "ADMIN", "admin", "SOVEREIGNT"])
    iso_col = _detect_col(gdf.columns, ["ISO_A3", "iso_a3", "ADM0_A3", "adm0_a3", "GID_0"])

    print(f"[GeoJSON] Using name='{name_col}', iso='{iso_col}'")

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            skipped += 1
            continue

        name = str(row.get(name_col, "Unknown")) if name_col else "Unknown"
        iso_a3 = str(row.get(iso_col, "XXX")) if iso_col else "XXX"

        try:
            contour_raw = _geometry_to_contour(geom, strategy)
        except Exception as exc:
            print(f"  [WARN] Skipping {name} ({iso_a3}): {exc}")
            skipped += 1
            continue

        try:
            entry = _make_entry(name, iso_a3, contour_raw, scale_method)
        except Exception as exc:
            print(f"  [WARN] Skipping {name} ({iso_a3}) — normalization failed: {exc}")
            skipped += 1
            continue

        entries.append(entry)

    print(f"[GeoJSON] Done. {len(entries)} countries cached, {skipped} skipped.")
    return entries


def _detect_col(columns, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def _geometry_to_contour(geom, strategy: str) -> np.ndarray:
    """
    Convert a Shapely geometry (Polygon or MultiPolygon) to an
    OpenCV-compatible contour array (N, 1, 2), dtype int32.
    """
    from shapely.geometry import MultiPolygon, Polygon

    polygons: list = []

    if geom.geom_type == "Polygon":
        polygons = [geom]
    elif geom.geom_type == "MultiPolygon":
        polygons = list(geom.geoms)
    else:
        # Attempt to extract polygons from GeometryCollection
        polygons = [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]

    if not polygons:
        raise ValueError(f"No polygons found in geometry type '{geom.geom_type}'")

    if strategy == "largest_only":
        poly = max(polygons, key=lambda p: p.area)
        coords = np.array(poly.exterior.coords, dtype=np.float32)
    elif strategy == "all_merged":
        # Keep a valid contour without introducing artificial bridges between disconnected
        # polygon components. For the first implementation, the largest polygon is the stable
        # representative of the country's main outline.
        poly = max(polygons, key=lambda p: p.area)
        coords = np.array(poly.exterior.coords, dtype=np.float32)
    else:
        raise ValueError(f"Unknown strategy: '{strategy}'")

    if len(coords) < 3:
        raise ValueError("Too few coordinates after extraction.")

    # GeoJSON longitude/latitude are in a geographic CRS: Y increases northward.
    # Image contours use image space: Y increases downward. Convert to a common planar
    # convention before matching and then mirror the Y-axis to match the chapati contour.
    coords[:, 1] = -coords[:, 1]
    return coords[:, np.newaxis, :].astype(np.float32)


# -------------------------------------------------------------------
# SVG pipeline (fallback / experimental)
# -------------------------------------------------------------------
def _load_svg(svg_path: Path, strategy: str, scale_method: str) -> list[CountryEntry]:
    """
    Parse WRI whole-world SVG → per-country contours.

    The WRI SVGs are whole-world maps where each <path> element represents
    one country polygon/fragment. They are grouped in <g> elements but the
    per-country identity is NOT encoded in path IDs (they're all blank).

    Strategy: use the intl_wintri.svg group 0 (fill=#ddd) which contains
    the solid country fills. Each <path d="..."> is ONE country polygon
    (or one fragment of a multi-part country). We treat each path as its own
    contour and try to group them by proximity — but since there's no ID,
    this is a best-effort heuristic.

    For a production-quality result, prefer the GeoJSON route.
    """
    try:
        from svgpathtools import parse_path
    except ImportError:
        # Fall back to a minimal SVG path parser
        parse_path = None

    import re
    from xml.etree import ElementTree as ET

    print(f"[SVG] Loading {svg_path} ...")
    tree = ET.parse(str(svg_path))
    root = tree.getroot()

    NS = "http://www.w3.org/2000/svg"

    # Grab the first filled group — country fills
    filled_group = None
    for g in root.iter(f"{{{NS}}}g"):
        fill = g.get("fill", "")
        gid = g.get("id", "")
        if fill == "#ddd" or gid == "0":
            filled_group = g
            break

    if filled_group is None:
        raise RuntimeError("Could not locate the country fill group in the SVG.")

    path_elements = list(filled_group.iter(f"{{{NS}}}path"))
    if not path_elements:
        # Try without namespace
        path_elements = list(filled_group.iter("path"))

    print(f"[SVG] Found {len(path_elements)} path elements in fill group.")

    entries: list[CountryEntry] = []
    skipped = 0

    for i, pel in enumerate(path_elements):
        d = pel.get("d", "")
        if not d:
            skipped += 1
            continue

        coords = _parse_svg_path_to_coords(d)
        if coords is None or len(coords) < 3:
            skipped += 1
            continue

        contour_raw = coords[:, np.newaxis, :].astype(np.float32)

        # No ISO/name info in SVG — use sequential index
        name = f"country_{i:04d}"
        iso_a3 = f"SV{i:03d}"

        try:
            entry = _make_entry(name, iso_a3, contour_raw, scale_method)
        except Exception as exc:
            skipped += 1
            continue

        entries.append(entry)

    print(f"[SVG] Done. {len(entries)} paths processed, {skipped} skipped.")
    print("  [NOTE] SVG paths have no country names/ISO codes. Use GeoJSON for named results.")
    return entries


def _parse_svg_path_to_coords(d: str) -> np.ndarray | None:
    """
    Minimal SVG 'd' attribute parser for the WRI SVG format.
    WRI paths use absolute M / L commands with space-separated coordinate pairs.
    e.g. "M 420.1 286.1 420.3 284.0 ... Z"
    Returns array of shape (N, 2), float32, or None on failure.
    """
    import re

    # Remove command letters and split into numbers
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    if len(nums) < 6:  # Need at least 3 points
        return None

    try:
        floats = [float(x) for x in nums]
    except ValueError:
        return None

    # Pair up: x0, y0, x1, y1, ...
    if len(floats) % 2 != 0:
        floats = floats[:-1]  # Drop trailing unpaired number

    coords = np.array(floats, dtype=np.float32).reshape(-1, 2)
    return coords if len(coords) >= 3 else None


# -------------------------------------------------------------------
# Shared: make a CountryEntry from a raw contour
# -------------------------------------------------------------------
def _make_entry(
    name: str,
    iso_a3: str,
    contour_raw: np.ndarray,
    scale_method: str,
) -> CountryEntry:
    """Normalize contour, compute Hu moments, build cache entry."""
    # Bounding box & area before normalization
    x, y, w, h = cv2.boundingRect(contour_raw.astype(np.int32))
    raw_area = float(cv2.contourArea(contour_raw))
    raw_bbox = [float(x), float(y), float(x + w), float(y + h)]

    # Normalize
    contour_norm = normalize_contour(contour_raw, scale_method)

    # Hu moments on the normalized contour (for fast matching)
    moments = cv2.moments(contour_norm)
    hu = cv2.HuMoments(moments).flatten().tolist()

    return CountryEntry(
        iso_a3=iso_a3,
        name=name,
        contour_points=contour_to_list(contour_norm),
        hu_moments=hu,
        raw_area=raw_area,
        raw_bbox=raw_bbox,
    )


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def build_cache(config_path: Path | None = None) -> None:
    cfg = load_settings(config_path)
    cd = cfg.country_data
    nm = cfg.normalization

    source = cd.source
    strategy = cd.polygon_selection_strategy
    scale_method = nm.scale_norm_method

    cache_path = cfg.resolve(cd.cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    if source == "geojson":
        geojson_path = cfg.resolve(cd.geojson_path)
        if not geojson_path.exists():
            raise FileNotFoundError(
                f"GeoJSON not found at {geojson_path}.\n"
                "Download it from:\n"
                "  https://raw.githubusercontent.com/wri/wri-bounds/master/dist/all_primary_countries.geojson\n"
                "and place it at backend/data/all_primary_countries.geojson"
            )
        entries = _load_geojson(geojson_path, strategy, scale_method)
        source_path = str(geojson_path)

    elif source == "svg":
        svg_path = cfg.resolve(cd.svg_path)
        if not svg_path.exists():
            raise FileNotFoundError(f"SVG not found at {svg_path}.")
        entries = _load_svg(svg_path, strategy, scale_method)
        source_path = str(svg_path)

    else:
        raise ValueError(f"Unknown data source: '{source}'. Use 'geojson' or 'svg'.")

    elapsed = time.time() - t0

    import datetime
    metadata: CacheMetadata = {
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
        "source_path": source_path,
        "polygon_strategy": strategy,
        "scale_norm_method": scale_method,
        "n_countries": len(entries),
        "attribution": (
            "Country boundary data: WRI (CC0-1.0), "
            "based on Natural Earth Data. "
            "These boundaries do not imply any opinion on legal status or "
            "endorsement of areas or boundaries."
        ),
    }

    payload = {"metadata": metadata, "countries": entries}

    with open(cache_path, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\n[OK] Cache saved to {cache_path}")
    print(f"     {len(entries)} countries | {elapsed:.1f}s")
    print(f"     Source: {source} | Strategy: {strategy} | Scale: {scale_method}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build country contour cache for RotiWorld.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: same directory as this script)",
    )
    args = parser.parse_args()
    build_cache(args.config)
