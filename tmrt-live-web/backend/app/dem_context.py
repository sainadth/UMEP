from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

try:
    import rasterio
except Exception:  # pragma: no cover
    rasterio = None

try:
    from rasterio.warp import (
        calculate_default_transform,
        reproject,
        transform as rio_transform,
    )
    from rasterio.enums import Resampling as _Resampling
except Exception:  # pragma: no cover
    calculate_default_transform = None
    reproject = None
    rio_transform = None
    _Resampling = None

try:
    from pyproj import Transformer
except Exception:  # pragma: no cover
    Transformer = None


def _configure_proj_paths() -> None:
    # On some Windows setups, PROJ_LIB points to a PostGIS folder with an incompatible proj.db.
    # Prefer rasterio's bundled proj_data when available.
    if rasterio is None:
        return

    proj_data = Path(rasterio.__file__).resolve().parent / "proj_data"
    if proj_data.exists():
        os.environ["PROJ_LIB"] = str(proj_data)
        os.environ["PROJ_DATA"] = str(proj_data)


_configure_proj_paths()


@dataclass
class DemContext:
    dem_id: str
    name: str
    path: str
    crs: str | None
    width: int
    height: int
    bounds: dict[str, float]
    min_elev: float
    max_elev: float
    elevation: np.ndarray
    slope_norm: np.ndarray
    roughness_norm: np.ndarray
    transform: Any


DEM_REGISTRY: dict[str, DemContext] = {}


def _is_valid_array(arr: np.ndarray) -> np.ndarray:
    out = arr.astype(np.float32, copy=True)
    out[~np.isfinite(out)] = np.nan
    return out


def _normalize(arr: np.ndarray) -> np.ndarray:
    valid = np.isfinite(arr)
    if not np.any(valid):
        return np.zeros_like(arr, dtype=np.float32)
    amin = float(np.nanmin(arr))
    amax = float(np.nanmax(arr))
    if amax <= amin:
        return np.zeros_like(arr, dtype=np.float32)
    out = (arr - amin) / (amax - amin)
    out[~valid] = 0.0
    return out.astype(np.float32)


def _compute_slope_roughness(elevation: np.ndarray, transform: Any) -> tuple[np.ndarray, np.ndarray]:
    # Fallback pixel size if transform metadata is missing.
    dx = float(abs(transform.a)) if transform is not None else 1.0
    dy = float(abs(transform.e)) if transform is not None else 1.0
    dx = dx if dx > 0 else 1.0
    dy = dy if dy > 0 else 1.0

    # Replace NaNs for gradient math, then restore masked semantics by normalization.
    filled = np.where(np.isfinite(elevation), elevation, np.nanmean(elevation))
    gy, gx = np.gradient(filled, dy, dx)
    slope_rad = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(slope_rad)

    # Roughness proxy from local gradient magnitude.
    roughness = np.sqrt(gx * gx + gy * gy)

    return _normalize(slope_deg), _normalize(roughness)


_TARGET_CRS = "EPSG:4326"


def _reproject_to_wgs84(src) -> tuple[np.ndarray, Any, int, int]:
    """Reproject band-1 data from src to EPSG:4326. Returns (array, transform, width, height)."""
    nodata = src.nodata
    raw = src.read(1).astype(np.float32)
    if nodata is not None:
        raw[raw == nodata] = np.nan

    if (
        src.crs is None
        or calculate_default_transform is None
        or reproject is None
        or _Resampling is None
    ):
        # No CRS info or warp tools unavailable — assume already WGS84.
        return raw, src.transform, src.width, src.height

    # Skip reprojection when already geographic WGS84.
    try:
        if src.crs.to_epsg() == 4326:
            return raw, src.transform, src.width, src.height
    except Exception:
        pass

    dst_transform, dst_width, dst_height = calculate_default_transform(
        src.crs, _TARGET_CRS, src.width, src.height, *src.bounds
    )
    arr = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
    reproject(
        source=raw,
        destination=arr,
        src_transform=src.transform,
        src_crs=src.crs,
        dst_transform=dst_transform,
        dst_crs=_TARGET_CRS,
        src_nodata=nodata,
        dst_nodata=np.nan,
        resampling=_Resampling.bilinear,
    )
    return arr, dst_transform, int(dst_width), int(dst_height)


def load_dem_file(file_path: Path, original_name: str) -> DemContext:
    if rasterio is None:
        raise RuntimeError("rasterio is required for DEM ingestion. Install dependencies from requirements.txt.")

    with rasterio.open(file_path) as src:
        arr, used_transform, width, height = _reproject_to_wgs84(src)

    arr = _is_valid_array(arr)
    slope_norm, roughness_norm = _compute_slope_roughness(arr, used_transform)

    valid = np.isfinite(arr)
    if not np.any(valid):
        raise RuntimeError("DEM contains no valid elevation values.")

    min_elev = float(np.nanmin(arr))
    max_elev = float(np.nanmax(arr))

    # Bounds are now always in EPSG:4326 (lon/lat).
    west = float(used_transform.c)
    north = float(used_transform.f)
    east = float(west + used_transform.a * width)
    south = float(north + used_transform.e * height)
    bounds = {
        "left": min(west, east),
        "bottom": min(south, north),
        "right": max(west, east),
        "top": max(south, north),
    }

    dem_id = str(uuid.uuid4())
    context = DemContext(
        dem_id=dem_id,
        name=original_name,
        path=str(file_path),
        crs=_TARGET_CRS,
        width=width,
        height=height,
        bounds=bounds,
        min_elev=min_elev,
        max_elev=max_elev,
        elevation=arr,
        slope_norm=slope_norm,
        roughness_norm=roughness_norm,
        transform=used_transform,
    )
    DEM_REGISTRY[dem_id] = context
    return context


def list_dems() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for dem in DEM_REGISTRY.values():
        items.append(
            {
                "dem_id": dem.dem_id,
                "name": dem.name,
                "crs": dem.crs,
                "width": dem.width,
                "height": dem.height,
                "bounds": dem.bounds,
                "min_elev": dem.min_elev,
                "max_elev": dem.max_elev,
            }
        )
    return items


def _latlon_to_dataset_xy(dem: DemContext, lat: float, lon: float) -> tuple[float, float]:
    # DEM arrays are always stored in EPSG:4326 after load_dem_file reprojection.
    return lon, lat


def sample_dem(dem_id: str, lat: float, lon: float) -> dict[str, float] | None:
    dem = DEM_REGISTRY.get(dem_id)
    if dem is None:
        return None

    x, y = _latlon_to_dataset_xy(dem, lat, lon)

    if rasterio is None:
        return None

    row, col = rasterio.transform.rowcol(dem.transform, x, y)

    if row < 0 or col < 0 or row >= dem.height or col >= dem.width:
        return None

    elev = float(dem.elevation[row, col]) if np.isfinite(dem.elevation[row, col]) else np.nan
    slope_n = float(dem.slope_norm[row, col])
    rough_n = float(dem.roughness_norm[row, col])

    if not np.isfinite(elev):
        return None

    elev_span = max(1e-6, dem.max_elev - dem.min_elev)
    elev_norm = (elev - dem.min_elev) / elev_span

    return {
        "elev_m": elev,
        "elev_norm": float(max(0.0, min(1.0, elev_norm))),
        "slope_norm": float(max(0.0, min(1.0, slope_n))),
        "roughness_norm": float(max(0.0, min(1.0, rough_n))),
    }
