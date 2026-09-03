# RotiWorld / Chapati World

A deliberately useless computer-vision app that photographs a misshapen chapati and tries to tell you which country its outline most resembles.

## Live demo
- Backend API: https://roti-world.onrender.com
- Health check: https://roti-world.onrender.com/api/health

## Team
- Team: TrustMeBro
- Evan Paul Gibi — Govt Model Engineering College
- Aaron S Christo — Govt Model Engineering College
- Event: TinkerHub Useless Projects 3.0

## What the project does
1. Upload a chapati image.
2. Detect the outer contour with OpenCV.
3. Normalize and compare the contour against cached country outlines.
4. Return the closest country and a leaderboard of suspiciously similar nations.

## Architecture

### Offline pipeline
`backend/build_country_cache.py` reads the GeoJSON country data, normalizes the country contours, and writes the cache to `backend/cache/country_cache.pkl`.

### Online pipeline
`backend/chapati.py` handles image decoding, thresholding, contour extraction, and overlay rendering.
`backend/normalize.py` uses geometric normalization and contour alignment.
`backend/matcher.py` ranks country matches and returns the leaderboard.
`backend/share.py` renders a shareable PNG card.

## Tech stack
- Python 3.11+
- FastAPI + uvicorn
- OpenCV + NumPy
- Pillow
- GeoPandas + Shapely
- PyYAML
- HTML/CSS/JS frontend

## Local setup
```bash
cd /home/bloodhat/WebDev/useless_project_temp/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python build_country_cache.py
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Frontend local run
```bash
cd /home/bloodhat/WebDev/useless_project_temp/frontend
python3 -m http.server 8001
```

## Project structure
```text
.
├── README.md
├── PROJECT_BRIEF.MD
├── backend/
│   ├── build_country_cache.py
│   ├── chapati.py
│   ├── config.py
│   ├── config.yaml
│   ├── main.py
│   ├── matcher.py
│   ├── normalize.py
│   ├── requirements.txt
│   ├── share.py
│   ├── cache/
│   ├── data/
│   └── svgs/
├── frontend/
│   ├── config.js
│   ├── index.html
│   ├── script.js
│   ├── styles.css
│   └── assets/
└── backend/tests/
```

## Screenshots

### App landing page
The frontend lets a user upload a chapati image and inspect the detected outline before confirmation.

### Result screen
The backend returns the best country match and a leaderboard of close contenders.

### Share card output
The generated share card includes the winning country, score, and top matches without missing emoji glyphs.

## Demo notes
- The app is intended as a playful “useless project” rather than a scientifically rigorous geographic classifier.
- The geometry matcher is tuned for contour similarity and explicit confirmation before matching.

## Team contributions
- Evan Paul Gibi — backend matching, country cache pipeline, deployment and project integration
- Aaron S Christo — frontend flow, UI polish, and project presentation

---
Made with ❤️ at TinkerHub Useless Projects 3.0.


