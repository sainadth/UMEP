# Live TMRT 2D Web App (Fullstack)

A lightweight fullstack prototype for live 2D TMRT prediction:

- Backend: FastAPI (`backend/app/main.py`)
- Frontend: Leaflet web UI (`backend/app/static/index.html`)
- Live weather source: Open-Meteo API
- TMRT engine: fast SOLWEIG-inspired approximation

## What this does

1. Fetches live weather (`Ta`, `RH`, `Ws`, `radG`, `radD`, `radI`, `P`) from Open-Meteo.
2. Computes sun altitude/azimuth from location + timestamp.
3. Runs a fast 2D TMRT prediction over a configurable map grid.
4. Renders a colorized TMRT heatmap layer in the browser.
5. Supports optional DEM upload (GeoTIFF) and DEM-informed terrain proxies in TMRT.
6. Supports optional DSM upload and georeferenced DSM image overlay in the map.
7. Includes a basemap switcher (street / satellite).

## Important limitation

This is **not** full SOLWEIG radiative transfer. It is an operational approximation designed for web-speed updates.

## Run locally

From `tmrt-live-web/backend`:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

## API endpoints

- `GET /health`
- `GET /api/weather/live?lat=57.7089&lon=11.9746`
- `GET /api/tmrt/grid?lat=57.7089&lon=11.9746&grid_size=40&span_m=1200`
- `GET /api/dem/list`
- `POST /api/dem/upload` (multipart form field name: `file`)
- `GET /api/dsm/list`
- `POST /api/dsm/upload` (multipart form field name: `file`)
- `GET /api/dsm/{dsm_id}/overlay`
- `GET /api/dsm/{dsm_id}/image.png`
- `GET /api/tmrt/grid?lat=27.713651&lon=-97.325456&grid_size=40&span_m=1200&dem_id=<id>`

## Tuning ideas

- Replace procedural urban morphology with your real SVF/shadow rasters.
- Add caching for weather requests.
- Replace simplified TMRT kernel with tighter SOLWEIG coupling for production.
