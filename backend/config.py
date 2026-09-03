"""
config.py — Single source of truth for RotiWorld configuration.
Loads config.yaml and exposes a typed Settings dataclass.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Literal, get_type_hints

import yaml


@dataclass
class CountryDataConfig:
    source: Literal["svg", "geojson"] = "geojson"
    svg_path: str = "./svgs/intl_wintri.svg"
    geojson_path: str = "./data/all_primary_countries.geojson"
    polygon_selection_strategy: Literal["largest_only", "all_merged"] = "largest_only"
    cache_path: str = "./cache/country_cache.pkl"


@dataclass
class ImageProcessingConfig:
    max_upload_mb: int = 10
    blur_kernel: int = 7
    threshold_method: Literal["otsu", "adaptive_gaussian"] = "otsu"
    morph_kernel: int = 5
    min_contour_area_ratio: float = 0.02
    simplify_epsilon_pct: float = 0.5
    ambiguous_area_margin: float = 0.1


@dataclass
class NormalizationConfig:
    scale_norm_method: Literal["bounding_box_diagonal", "sqrt_area", "max_radius"] = "bounding_box_diagonal"


@dataclass
class MatchingConfig:
    primary_method: Literal["CONTOURS_MATCH_I1", "CONTOURS_MATCH_I2", "CONTOURS_MATCH_I3"] = "CONTOURS_MATCH_I1"
    score_formula: Literal["exponential", "linear_clamped"] = "exponential"
    score_k: float = 5.0
    leaderboard_size: int = 5
    secondary_metric_enabled: bool = False


@dataclass
class CopyConfig:
    templates_path: str = "./data/result_copy.json"


@dataclass
class Settings:
    country_data: CountryDataConfig = field(default_factory=CountryDataConfig)
    image_processing: ImageProcessingConfig = field(default_factory=ImageProcessingConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    copy: CopyConfig = field(default_factory=CopyConfig)
    # Base directory (set at load time so all relative paths resolve correctly)
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)

    def resolve(self, rel_path: str) -> Path:
        """Resolve a relative path from config relative to base_dir."""
        return (self.base_dir / rel_path).resolve()


def _load_dataclass(cls, data: dict):
    """Recursively instantiate nested dataclasses from a dict."""
    if not isinstance(data, dict):
        return data
    hints = get_type_hints(cls)
    kwargs = {}
    for key, val in data.items():
        if key not in cls.__dataclass_fields__:
            continue
        field_type = hints.get(key)
        if field_type is not None and hasattr(field_type, "__dataclass_fields__"):
            kwargs[key] = _load_dataclass(field_type, val)
        else:
            kwargs[key] = val
    return cls(**kwargs)


def load_settings(config_path: str | Path | None = None) -> Settings:
    """
    Load settings from config.yaml.
    Falls back to defaults if the file doesn't exist.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    config_path = Path(config_path)

    if not config_path.exists():
        return Settings()

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    settings = Settings()
    if "country_data" in raw:
        settings.country_data = _load_dataclass(CountryDataConfig, raw["country_data"])
    if "image_processing" in raw:
        settings.image_processing = _load_dataclass(ImageProcessingConfig, raw["image_processing"])
    if "normalization" in raw:
        settings.normalization = _load_dataclass(NormalizationConfig, raw["normalization"])
    if "matching" in raw:
        settings.matching = _load_dataclass(MatchingConfig, raw["matching"])
    if "copy" in raw:
        settings.copy = _load_dataclass(CopyConfig, raw["copy"])

    settings.base_dir = config_path.parent
    return settings


# Module-level singleton — import this everywhere
settings: Settings = load_settings()
