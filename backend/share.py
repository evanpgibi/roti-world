"""
share.py — Server-side shareable card generation (Pillow).

Composes a branded card image:
  ┌──────────────────────────────────────────┐
  │  🌍  CHAPATI WORLD                       │
  │  Your chapati is 87.3% Madagascar        │
  │  [chapati outline]  [country outline]    │
  │  🥇 Madagascar 87.3%                     │
  │  🥈 Sri Lanka   71.0%                    │
  │  🥉 ...                                  │
  │  boundary data: WRI (CC0)               │
  └──────────────────────────────────────────┘

Returns raw PNG bytes.
"""
from __future__ import annotations

import io
import math
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


CARD_W = 900
CARD_H = 520
BG_COLOR = (15, 15, 25)          # near-black
ACCENT    = (120, 220, 120)       # neon green
GOLD      = (255, 215, 0)
TEXT_MAIN = (240, 240, 240)
TEXT_DIM  = (150, 150, 160)
CHAPATI_COLOR = (255, 180, 60)    # warm orange for chapati outline
COUNTRY_COLOR = (100, 200, 255)   # cyan for country outline


def _try_load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Load a system font or fall back to default."""
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _draw_outline(
    draw: ImageDraw.ImageDraw,
    points: list[list[float]],
    center_x: int,
    center_y: int,
    size: int,
    color: tuple[int, int, int],
    line_width: int = 2,
) -> None:
    """
    Draw a normalized contour (centered at 0, scale ≈ ±0.5) onto the card.

    Parameters
    ----------
    center_x, center_y : int
        Pixel center for the drawing.
    size : int
        Half-size in pixels (contour fits within ±size).
    """
    if not points:
        return

    # Map normalized coords (≈ -0.5..0.5) to pixel space
    pts_px = [
        (int(center_x + p[0] * size), int(center_y + p[1] * size))
        for p in points
    ]

    if len(pts_px) < 2:
        return

    # Draw as polygon
    draw.polygon(pts_px, outline=color)
    # Thicken by drawing slightly offset outlines
    if line_width > 1:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            shifted = [(x + dx, y + dy) for x, y in pts_px]
            draw.polygon(shifted, outline=color)


def generate_share_card(
    best_country: str,
    best_iso: str,
    best_score: float,
    leaderboard: list[dict],           # [{country, iso_a3, score}, ...]
    chapati_outline: list[list[float]],
    country_outline: list[list[float]],
    playful_copy: str,
    overlay_image_b64: Optional[str] = None,
) -> bytes:
    """
    Generate a shareable PNG card and return raw bytes.
    """
    card = Image.new("RGB", (CARD_W, CARD_H), color=BG_COLOR)
    draw = ImageDraw.Draw(card)

    # --- Fonts ---
    font_title  = _try_load_font(28, bold=True)
    font_large  = _try_load_font(22, bold=True)
    font_medium = _try_load_font(16)
    font_small  = _try_load_font(13)
    font_tiny   = _try_load_font(11)

    # --- Header bar ---
    draw.rectangle([0, 0, CARD_W, 60], fill=(25, 25, 40))
    draw.text((24, 16), "🌍  CHAPATI WORLD", font=font_title, fill=ACCENT)

    # --- Tagline ---
    draw.text(
        (24, 76),
        playful_copy,
        font=font_large,
        fill=TEXT_MAIN,
    )

    # --- Outline comparison panels ---
    panel_y = 130
    panel_h = 220
    panel_chapati_x = 80
    panel_country_x = 470

    # Panel backgrounds
    for px in [panel_chapati_x, panel_country_x]:
        draw.rectangle(
            [px - 5, panel_y - 5, px + 320, panel_y + panel_h + 5],
            outline=(50, 50, 70),
            width=1,
        )

    # Labels
    draw.text((panel_chapati_x + 80, panel_y - 22), "Your Chapati", font=font_small, fill=TEXT_DIM)
    draw.text((panel_country_x + 60, panel_y - 22), best_country, font=font_small, fill=TEXT_DIM)

    # Contour center points
    cy = panel_y + panel_h // 2
    cx_chapati = panel_chapati_x + 155
    cx_country = panel_country_x + 155

    _draw_outline(draw, chapati_outline, cx_chapati, cy, 90, CHAPATI_COLOR, line_width=2)
    _draw_outline(draw, country_outline, cx_country, cy, 90, COUNTRY_COLOR, line_width=2)

    # Score badge
    score_txt = f"{best_score:.1f}%"
    draw.text((CARD_W // 2 - 30, panel_y + panel_h // 2 - 15), score_txt, font=font_large, fill=GOLD)

    # --- Leaderboard ---
    lb_y = panel_y + panel_h + 20
    draw.text((24, lb_y), "Top matches:", font=font_small, fill=TEXT_DIM)
    lb_y += 20
    medals = ["🥇", "🥈", "🥉", "  4.", "  5."]
    for i, entry in enumerate(leaderboard[:5]):
        medal = medals[i] if i < len(medals) else f"  {i+1}."
        line = f"{medal}  {entry['country']}  —  {entry['score']:.1f}%"
        color = GOLD if i == 0 else TEXT_MAIN
        draw.text((24, lb_y + i * 20), line, font=font_small, fill=color)

    # --- Footer ---
    draw.rectangle([0, CARD_H - 28, CARD_W, CARD_H], fill=(20, 20, 35))
    draw.text(
        (24, CARD_H - 20),
        "boundary data: WRI (CC0-1.0) · chapatiworld.fun",
        font=font_tiny,
        fill=TEXT_DIM,
    )

    # --- Export ---
    buf = io.BytesIO()
    card.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
