# RotiWorld / Chapati World — Frontend API Documentation & Schema

This document details the backend REST API specifications for frontend developers building the Chapati World user interface.

- **Base URL (Local Development):** `http://localhost:8000`
- **CORS:** Enabled for all origins (`*`) with support for all standard headers and methods.
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 1. Core User Flow Overview

The application uses a 2-stage verification pipeline to ensure optimal UX and prevent wasted computation on poor uploads:

```
┌─────────────────────────┐
│ 1. User selects / snaps │
│    photo of chapati     │
└───────────┬─────────────┘
            │
            ▼ POST /api/analyze (multipart/form-data)
┌───────────────────────────────────────────────┐
│ 2. Backend extracts outline                   │
│    Returns: raw contour + overlay_image_b64   │
└───────────┬───────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────┐
│ 3. Frontend displays overlay image preview    │
│    "Is this your chapati?"                    │
│    User clicks [Confirm] or [Retake Photo]    │
└───────────┬───────────────────────────────────┘
            │
            ▼ POST /api/match (JSON: { contour })
┌───────────────────────────────────────────────┐
│ 4. Backend compares against 190+ countries    │
│    Returns: best_match, leaderboard,          │
│    normalized coordinate arrays, copy text    │
└───────────┬───────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────┐
│ 5. Frontend renders interactive result cards, │
│    side-by-side / overlaid outlines, & share  │
└───────────────────────────────────────────────┘
```

---

## 2. API Endpoints

### 2.1 `GET /api/health`
Health check and cache readiness indicator.

- **Method:** `GET`
- **URL:** `/api/health`
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "cache_ready": true,
  "n_countries": 193
}
```

---

### 2.2 `POST /api/analyze`
Accepts an uploaded image file, detects the primary chapati contour, and produces a preview overlay image.

- **Method:** `POST`
- **URL:** `/api/analyze`
- **Content-Type:** `multipart/form-data`
- **Request Parameters:**
  - `image` (File, required): Chapati photo file (`image/jpeg`, `image/png`, or HEIC). Max size: 10 MB (configurable in backend).

#### Success Response: `200 OK`
```json
{
  "detected_contour": [
    [154.0, 210.0],
    [155.0, 215.0],
    [158.0, 225.0]
  ],
  "overlay_image_b64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "image_width": 1080,
  "image_height": 1440,
  "contour_area_ratio": 0.342,
  "multiple_candidates": false,
  "candidate_contours": [],
  "confirm_required": true
}
```

#### Response Fields:
| Field | Type | Description |
|---|---|---|
| `detected_contour` | `number[][]` | Array of `[x, y]` coordinates in original image pixel space. Send this to `/api/match`. |
| `overlay_image_b64` | `string` | Base64-encoded PNG string showing original image with the green detected outline drawn on top. |
| `image_width` | `number` | Width of the uploaded image in pixels. |
| `image_height` | `number` | Height of the uploaded image in pixels. |
| `contour_area_ratio` | `number` | Ratio of contour area to overall image area (e.g. `0.342` = 34.2%). |
| `multiple_candidates` | `boolean` | `true` if multiple similar-sized objects were detected (e.g., two chapatis or plate boundary). |
| `candidate_contours` | `number[][][]` | Array of alternative contours if `multiple_candidates` is `true`. |
| `confirm_required` | `boolean` | Always `true`. Signals the UI to present the confirmation modal. |

#### Error Responses:
- **`413 Payload Too Large`**:
  ```json
  {
    "detail": {
      "error": true,
      "code": "FILE_TOO_LARGE",
      "message": "Image exceeds 10 MB limit. Please compress or crop your photo."
    }
  }
  ```
- **`400 Bad Request`**:
  ```json
  {
    "detail": {
      "error": true,
      "code": "NO_CONTOUR",
      "message": "No outline detected. Try placing your chapati on a plain, high-contrast surface..."
    }
  }
  ```
  *Possible `code` values:*
  - `DECODE_FAILED`: File format invalid or corrupted.
  - `NO_CONTOUR`: No closed shape found.
  - `TOO_SMALL`: Shape found, but smaller than minimum area ratio (< 2%).

---

### 2.3 `POST /api/match`
Takes the confirmed contour points and evaluates similarity against all cached country shapes.

- **Method:** `POST`
- **URL:** `/api/match`
- **Content-Type:** `application/json`

#### Request Body:
```json
{
  "contour": [
    [154.0, 210.0],
    [155.0, 215.0],
    [158.0, 225.0]
  ]
}
```

#### Success Response: `200 OK`
```json
{
  "best_match": {
    "country": "Madagascar",
    "iso_a3": "MDG",
    "score": 87.3,
    "distance": 0.027142
  },
  "leaderboard": [
    {
      "country": "Madagascar",
      "iso_a3": "MDG",
      "score": 87.3,
      "distance": 0.027142
    },
    {
      "country": "Sri Lanka",
      "iso_a3": "LKA",
      "score": 71.0,
      "distance": 0.068412
    },
    {
      "country": "Sierra Leone",
      "iso_a3": "SLE",
      "score": 58.4,
      "distance": 0.107561
    },
    {
      "country": "Cyprus",
      "iso_a3": "CYP",
      "score": 52.1,
      "distance": 0.130398
    },
    {
      "country": "Uruguay",
      "iso_a3": "URY",
      "score": 48.9,
      "distance": 0.143055
    }
  ],
  "chapati_outline_normalized": [
    [-0.124, 0.451],
    [-0.118, 0.432]
  ],
  "country_outline_normalized": [
    [-0.131, 0.448],
    [-0.125, 0.429]
  ],
  "playful_copy": "Undeniable. Your chapati strongly resembles Madagascar at 87.3%."
}
```

#### Response Fields:
| Field | Type | Description |
|---|---|---|
| `best_match` | `object` | The #1 matching country object (`country`, `iso_a3`, `score`, `distance`). |
| `leaderboard` | `object[]` | Top 5 ranked countries with scores and distances. |
| `chapati_outline_normalized` | `number[][]` | Normalized `[x, y]` coordinates of the chapati outline (centered at 0, unit scale). |
| `country_outline_normalized` | `number[][]` | Normalized `[x, y]` coordinates of the winning country outline (same scale!). |
| `playful_copy` | `string` | Deadpan, humorous quote generated based on the match percentage. |

#### Error Responses:
- **`400 Bad Request`**:
  ```json
  {
    "detail": {
      "error": true,
      "code": "INVALID_CONTOUR",
      "message": "Contour must have at least 3 points."
    }
  }
  ```
- **`503 Service Unavailable`**:
  ```json
  {
    "detail": {
      "error": true,
      "code": "CACHE_MISSING",
      "message": "Country cache not found. Rebuild the cache."
    }
  }
  ```

---

### 2.4 `POST /api/share`
Generates a branded, server-side rendered PNG card ready for downloading or sharing to social media.

- **Method:** `POST`
- **URL:** `/api/share`
- **Content-Type:** `application/json`
- **Accept:** `image/png`

#### Request Body:
```json
{
  "best_country": "Madagascar",
  "best_iso": "MDG",
  "best_score": 87.3,
  "leaderboard": [
    { "country": "Madagascar", "iso_a3": "MDG", "score": 87.3 },
    { "country": "Sri Lanka", "iso_a3": "LKA", "score": 71.0 }
  ],
  "chapati_outline": [
    [-0.124, 0.451],
    [-0.118, 0.432]
  ],
  "country_outline": [
    [-0.131, 0.448],
    [-0.125, 0.429]
  ],
  "playful_copy": "Undeniable. Your chapati strongly resembles Madagascar at 87.3%."
}
```

#### Success Response: `200 OK`
- **Content-Type:** `image/png`
- **Body:** Binary PNG stream (dimensions: 900 × 520 px).

---

### 2.5 `GET /api/cache/info`
Provides metadata regarding the country database and attribution.

- **Method:** `GET`
- **URL:** `/api/cache/info`
- **Response `200 OK`:**
```json
{
  "built_at": "2026-09-03T17:46:57.451286+00:00",
  "source": "geojson",
  "source_path": ".../all_primary_countries.geojson",
  "polygon_strategy": "largest_only",
  "scale_norm_method": "bounding_box_diagonal",
  "n_countries": 193,
  "attribution": "Country boundary data: WRI (CC0-1.0), based on Natural Earth Data. These boundaries do not imply any opinion on legal status or endorsement of areas or boundaries."
}
```

---

## 3. TypeScript Type Definitions

You can copy-paste these types directly into your frontend project (e.g. `src/types/api.ts`):

```typescript
export type Point2D = [number, number];

export interface AnalyzeResponse {
  detected_contour: Point2D[];
  overlay_image_b64: string; // Base64 data (without "data:image/png;base64," prefix)
  image_width: number;
  image_height: number;
  contour_area_ratio: number;
  multiple_candidates: boolean;
  candidate_contours: Point2D[][];
  confirm_required: boolean;
}

export interface ApiErrorDetail {
  error: boolean;
  code: string;
  message: string;
}

export interface ApiErrorResponse {
  detail: ApiErrorDetail | string;
}

export interface CountryMatch {
  country: string;
  iso_a3: string;
  score: number;       // 0 to 100
  distance: number;    // Raw Hu moment distance
}

export interface MatchRequest {
  contour: Point2D[];
}

export interface MatchResponse {
  best_match: CountryMatch;
  leaderboard: CountryMatch[];
  chapati_outline_normalized: Point2D[];
  country_outline_normalized: Point2D[];
  playful_copy: string;
}

export interface ShareRequest {
  best_country: string;
  best_iso: string;
  best_score: number;
  leaderboard: Array<{
    country: string;
    iso_a3: string;
    score: number;
  }>;
  chapati_outline: Point2D[];
  country_outline: Point2D[];
  playful_copy: string;
}

export interface HealthResponse {
  status: "ok";
  cache_ready: boolean;
  n_countries: number;
}
```

---

## 4. Frontend Integration Guide & Code Snippets

### 4.1 Displaying the Preview Overlay
The `overlay_image_b64` from `POST /api/analyze` is a raw base64 string. Display it in an `<img>` tag:

```javascript
const imageSrc = `data:image/png;base64,${data.overlay_image_b64}`;
document.getElementById('preview-image').src = imageSrc;
```

### 4.2 Step 1: Uploading the Image
```typescript
async function analyzeChapati(file: File): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append('image', file);

  const response = await fetch('http://localhost:8000/api/analyze', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail?.message || 'Failed to analyze image');
  }

  return response.json();
}
```

### 4.3 Step 2: Confirming & Matching
```typescript
async function matchContour(contour: Point2D[]): Promise<MatchResponse> {
  const response = await fetch('http://localhost:8000/api/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contour }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail?.message || 'Matching failed');
  }

  return response.json();
}
```

### 4.4 Step 3: Downloading Share Card
```typescript
async function downloadShareCard(payload: ShareRequest): Promise<void> {
  const response = await fetch('http://localhost:8000/api/share', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chapati-${payload.best_country.toLowerCase()}.png`;
  a.click();
  window.URL.revokeObjectURL(url);
}
```

### 4.5 Rendering Normalized Outlines on HTML5 Canvas
Both `chapati_outline_normalized` and `country_outline_normalized` are centered at `(0, 0)` with coordinates roughly in range `[-0.5, 0.5]`.

To draw them on a canvas of width `W` and height `H`:

```javascript
function drawContour(canvas, points, strokeColor = '#00ff88', fillColor = 'rgba(0, 255, 136, 0.15)') {
  const ctx = canvas.getContext('2d');
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;
  // Scale so contour occupies ~80% of canvas
  const scale = Math.min(canvas.width, canvas.height) * 0.8;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!points || points.length < 2) return;

  ctx.beginPath();
  const startX = cx + points[0][0] * scale;
  const startY = cy + points[0][1] * scale;
  ctx.moveTo(startX, startY);

  for (let i = 1; i < points.length; i++) {
    const x = cx + points[i][0] * scale;
    const y = cy + points[i][1] * scale;
    ctx.lineTo(x, y);
  }
  ctx.closePath();

  ctx.fillStyle = fillColor;
  ctx.fill();

  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 3;
  ctx.lineJoin = 'round';
  ctx.stroke();
}
```

---

## 5. UI Status / Error Code Guide

| Code | HTTP | User-Facing Guidance |
|---|---|---|
| `FILE_TOO_LARGE` | `413` | Show: "Photo is larger than 10 MB. Please pick a smaller image or crop it." |
| `DECODE_FAILED` | `400` | Show: "Could not read this image file. Please upload a standard JPG or PNG." |
| `NO_CONTOUR` | `400` | Show: "Could not find your chapati! Place it on a plain, contrasting surface (e.g. dark surface for light chapati) with good lighting." |
| `TOO_SMALL` | `400` | Show: "The chapati seems too far away in the frame. Move the camera closer and retake." |
| `INVALID_CONTOUR` | `400` | Show: "Invalid shape points received. Please retake the photo." |
| `CACHE_MISSING` | `503` | Backend setup issue: Run `python backend/build_country_cache.py`. |
