# RotiWorld / Chapati World — Project Brief

## One-liner
Photograph a misshapen chapati → the app tells you which country its outline most resembles, with a similarity score and side-by-side comparison.

## Team
- Team: TrustMeBro
- Evan Paul Gibi — Govt Model Engineering College
- Aaron S Christo — Govt Model Engineering College
- Event: TinkerHub Useless Projects 3.0

## Architecture

### Offline pipeline (run once)
`build_country_cache.py` → parses WRI GeoJSON → normalizes country contours → `cache/country_cache.pkl`

### Online pipeline (per request)
Upload → `chapati.py` (grayscale/blur/threshold/morphology/findContours) → normalize → `matcher.py` (cv2.matchShapes × 195 countries) → score + leaderboard → FastAPI response

## Project Structure
```
.
├── API_SCHEMA.md            Complete API documentation & schema for frontend developers
├── PROJECT_BRIEF.MD         Project overview & architectural brief
├── RotiWorld_PRD.md         Original PRD
├── README.md                Submission documentation
├── index.html               Frontend entrypoint
└── backend/
    ├── main.py                  FastAPI app (endpoints: /api/analyze, /api/match, /api/share)
    ├── config.py                Settings loader (reads config.yaml)
    ├── config.yaml              All tunable parameters (single source of truth)
    ├── chapati.py               Image processing pipeline (contour detection)
    ├── normalize.py             Scale-invariant normalization (used by both pipelines)
    ├── matcher.py               Shape comparison engine (cv2.matchShapes + scoring)
    ├── share.py                 Shareable card generator (Pillow)
    ├── build_country_cache.py   Offline cache builder script
    ├── requirements.txt         Python dependencies
    ├── data/
    │   ├── all_primary_countries.geojson  WRI boundary data (CC0-1.0)
    │   └── result_copy.json               Playful copy templates
    ├── cache/
    │   └── country_cache.pkl              Built by build_country_cache.py (193 countries)
    └── svgs/
        └── intl_wintri.svg (etc.)         WRI whole-world SVGs (fallback source)
```

## Tech Stack
- **Backend**: Python 3.11+ · FastAPI · uvicorn
- **CV**: opencv-python (cv2.matchShapes, Hu moments)
- **Geo parsing**: geopandas + shapely
- **Image composition**: Pillow
- **Config**: PyYAML (config.yaml)
- **Frontend**: HTML/CSS/JS (index.html — TBD)

## Key Design Decisions
1. **GeoJSON over SVG** — WRI SVGs are whole-world composites without per-country IDs. GeoJSON is clean and directly parseable.
2. **Hu moments / matchShapes** — rotation, scale, and translation invariant out of the box. Size of chapati vs country doesn't matter.
3. **Config-driven** — every threshold, kernel size, and algorithm choice lives in `config.yaml`. No hardcoded magic numbers.
4. **Two-phase API** — `/api/analyze` returns the detected outline for user confirmation before `/api/match` runs the expensive comparison.

## Setup Commands
```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Build country cache (one-time)
cd backend && python build_country_cache.py

# 3. Start API
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Status
- [x] PRD read and understood
- [x] Backend structure designed
- [x] config.py — settings loader
- [x] normalize.py — contour normalization
- [x] chapati.py — image processing pipeline
- [x] matcher.py — shape matching engine
- [x] share.py — shareable card generator
- [x] build_country_cache.py — offline cache builder
- [x] main.py — FastAPI app
- [x] GeoJSON downloaded
- [x] Cache built (193 countries cached in `backend/cache/country_cache.pkl`)
- [x] API schema documented in `API_SCHEMA.md` for frontend development
- [ ] Frontend (index.html) — to build

