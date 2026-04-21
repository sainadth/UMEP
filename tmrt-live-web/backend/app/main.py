from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .dem_context import DEM_REGISTRY, list_dems, load_dem_file, sample_dem
from .dsm_overlay import DSM_REGISTRY, get_dsm_or_404, list_dsms, render_geotiff_overlay, upload_dsm
from .tmrt_model import generate_tmrt_grid_geojson
from .weather import fetch_live_weather

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data" / "dems"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DSM_DIR = BASE_DIR / "data" / "dsms"
DSM_DIR.mkdir(parents=True, exist_ok=True)
DEM_OVERLAY_DIR = BASE_DIR / "data" / "dem_overlays"
DEM_OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Live TMRT 2D Predictor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/weather/live")
async def api_live_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict:
    try:
        return await fetch_live_weather(lat, lon)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch live weather: {exc}") from exc


@app.get("/api/dem/list")
async def api_dem_list() -> dict:
    return {"dems": list_dems()}


@app.get("/api/dsm/list")
async def api_dsm_list() -> dict:
    return {"dsms": list_dsms()}


@app.post("/api/dem/upload")
async def api_dem_upload(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No DEM filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Only GeoTIFF DEM files are supported (.tif/.tiff).")

    safe_name = Path(file.filename).name
    save_path = DATA_DIR / safe_name

    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        dem = load_dem_file(save_path, safe_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load DEM: {exc}") from exc

    return {
        "dem_id": dem.dem_id,
        "name": dem.name,
        "crs": dem.crs,
        "bounds": dem.bounds,
        "min_elev": dem.min_elev,
        "max_elev": dem.max_elev,
        "width": dem.width,
        "height": dem.height,
    }


@app.post("/api/dsm/upload")
async def api_dsm_upload(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No DSM filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Only GeoTIFF DSM files are supported (.tif/.tiff).")

    safe_name = Path(file.filename).name
    save_path = DSM_DIR / safe_name

    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        dsm = upload_dsm(save_path, safe_name, DSM_DIR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load DSM: {exc}") from exc

    return {
        "dsm_id": dsm.dsm_id,
        "name": dsm.name,
        "crs": dsm.crs,
        "bounds_latlon": dsm.bounds_latlon,
        "min_val": dsm.min_val,
        "max_val": dsm.max_val,
        "width": dsm.width,
        "height": dsm.height,
    }


@app.get("/api/dsm/{dsm_id}/overlay")
async def api_dsm_overlay(dsm_id: str) -> dict:
    dsm = get_dsm_or_404(dsm_id)
    return {
        "dsm_id": dsm.dsm_id,
        "name": dsm.name,
        "bounds": [
            [dsm.bounds_latlon["south"], dsm.bounds_latlon["west"]],
            [dsm.bounds_latlon["north"], dsm.bounds_latlon["east"]],
        ],
        "image_url": f"/api/dsm/{dsm_id}/image.png",
        "min_val": dsm.min_val,
        "max_val": dsm.max_val,
    }


@app.get("/api/dsm/{dsm_id}/image.png")
async def api_dsm_image(dsm_id: str) -> FileResponse:
    dsm = get_dsm_or_404(dsm_id)
    return FileResponse(path=dsm.image_path, media_type="image/png")


@app.delete("/api/dem/{dem_id}")
async def api_dem_delete(dem_id: str) -> dict:
    dem = DEM_REGISTRY.pop(dem_id, None)
    if dem is None:
        raise HTTPException(status_code=404, detail="DEM not found")
    try:
        Path(dem.path).unlink(missing_ok=True)
    except Exception:
        pass
    overlay_img = DEM_OVERLAY_DIR / f"{dem_id}.png"
    try:
        overlay_img.unlink(missing_ok=True)
    except Exception:
        pass
    return {"deleted": dem_id}


@app.delete("/api/dsm/{dsm_id}")
async def api_dsm_delete(dsm_id: str) -> dict:
    dsm = DSM_REGISTRY.pop(dsm_id, None)
    if dsm is None:
        raise HTTPException(status_code=404, detail="DSM not found")
    try:
        Path(dsm.path).unlink(missing_ok=True)
    except Exception:
        pass
    try:
        Path(dsm.image_path).unlink(missing_ok=True)
    except Exception:
        pass
    return {"deleted": dsm_id}


@app.get("/api/dem/{dem_id}/overlay")
async def api_dem_overlay(dem_id: str) -> dict:
    dem = DEM_REGISTRY.get(dem_id)
    if dem is None:
        raise HTTPException(status_code=404, detail="DEM not found")

    image_path = DEM_OVERLAY_DIR / f"{dem_id}.png"
    bounds_latlon, _crs, min_val, max_val, width, height = render_geotiff_overlay(Path(dem.path), image_path)

    return {
        "dem_id": dem_id,
        "name": dem.name,
        "width": width,
        "height": height,
        "bounds": [
            [bounds_latlon["south"], bounds_latlon["west"]],
            [bounds_latlon["north"], bounds_latlon["east"]],
        ],
        "image_url": f"/api/dem/{dem_id}/image.png",
        "min_val": min_val,
        "max_val": max_val,
    }


@app.get("/api/dem/{dem_id}/image.png")
async def api_dem_image(dem_id: str) -> FileResponse:
    image_path = DEM_OVERLAY_DIR / f"{dem_id}.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="DEM overlay image not found. Request /api/dem/{dem_id}/overlay first.")
    return FileResponse(path=image_path, media_type="image/png")


@app.get("/api/tmrt/grid")
async def api_tmrt_grid(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    grid_size: int = Query(40, ge=10, le=100),
    span_m: float = Query(1200.0, ge=200, le=5000),
    dem_id: str | None = Query(None),
) -> dict:
    try:
        weather = await fetch_live_weather(lat, lon)
        dem_sampler = None
        if dem_id:
            dem_sampler = lambda la, lo: sample_dem(dem_id, la, lo)

        return generate_tmrt_grid_geojson(
            lat=lat,
            lon=lon,
            weather=weather,
            grid_size=grid_size,
            span_m=span_m,
            dem_sampler=dem_sampler,
            dem_id=dem_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to generate TMRT grid: {exc}") from exc
