from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import HTTPException

from .dem_context import _configure_proj_paths

try:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject, transform as rio_transform
except Exception:  # pragma: no cover
    rasterio = None
    Resampling = None
    calculate_default_transform = None
    reproject = None
    rio_transform = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


@dataclass
class DsmOverlay:
    dsm_id: str
    name: str
    path: str
    image_path: str
    crs: str | None
    width: int
    height: int
    min_val: float
    max_val: float
    bounds_latlon: dict[str, float]


DSM_REGISTRY: dict[str, DsmOverlay] = {}


def _array_to_png(arr: np.ndarray, valid_mask: np.ndarray, out_path: Path) -> tuple[float, float]:
    if Image is None:
        raise RuntimeError("Pillow is required for DSM overlay image generation.")

    data = arr.astype(np.float32)
    finite = np.isfinite(data)
    valid = finite & valid_mask.astype(bool)
    data[~valid] = np.nan

    if not np.any(valid):
        raise RuntimeError("DSM contains no valid pixels.")

    vmin = float(np.nanpercentile(data, 1))
    vmax = float(np.nanpercentile(data, 99))
    if vmax <= vmin:
        vmax = vmin + 1.0

    normalized = (data - vmin) / (vmax - vmin)
    normalized = np.clip(normalized, 0.0, 1.0)
    normalized = np.power(normalized, 0.85)

    # QGIS-like singleband gray stretch for terrain/building contrast.
    gray = np.zeros_like(data, dtype=np.uint8)
    gray[valid] = (normalized[valid] * 255.0).astype(np.uint8)

    rgba = np.zeros((gray.shape[0], gray.shape[1], 4), dtype=np.uint8)
    rgba[:, :, 0] = gray
    rgba[:, :, 1] = gray
    rgba[:, :, 2] = gray
    rgba[:, :, 3] = np.where(valid, 255, 0).astype(np.uint8)

    image = Image.fromarray(rgba, mode="RGBA")
    image.save(out_path, format="PNG")

    return vmin, vmax


def _bounds_to_latlon(src) -> dict[str, float]:
    if rio_transform is None:
        raise RuntimeError("rasterio.warp.transform is required for DSM georeferencing.")

    left, bottom, right, top = src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top

    if src.crs and src.crs.to_string() and "4326" in src.crs.to_string():
        return {
            "west": float(left),
            "south": float(bottom),
            "east": float(right),
            "north": float(top),
        }

    xs = [left, right, right, left]
    ys = [bottom, bottom, top, top]
    lon, lat = rio_transform(src.crs, "EPSG:4326", xs, ys)

    return {
        "west": float(min(lon)),
        "south": float(min(lat)),
        "east": float(max(lon)),
        "north": float(max(lat)),
    }


def render_geotiff_overlay(file_path: Path, image_path: Path) -> tuple[dict[str, float], str | None, float, float, int, int]:
    _configure_proj_paths()

    if rasterio is None:
        raise RuntimeError("rasterio is required for raster overlay generation.")

    with rasterio.open(file_path) as src:
        nodata = src.nodata
        crs_text = src.crs.to_string() if src.crs else None

        # Reproject to north-up EPSG:4326 so Leaflet imageOverlay can place it
        # without the rotated/skewed bounding-box artifact.
        if src.crs and calculate_default_transform and reproject and Resampling:
            dst_crs = "EPSG:4326"
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs,
                dst_crs,
                src.width,
                src.height,
                *src.bounds,
            )

            arr = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=arr,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=nodata,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )

            src_mask = src.read_masks(1).astype(np.uint8)
            dst_mask = np.zeros((dst_height, dst_width), dtype=np.uint8)
            reproject(
                source=src_mask,
                destination=dst_mask,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest,
            )

            valid_mask = (dst_mask > 0) & np.isfinite(arr)
            if nodata is not None:
                valid_mask &= arr != nodata

            left = float(dst_transform.c)
            top = float(dst_transform.f)
            right = float(left + dst_transform.a * dst_width)
            bottom = float(top + dst_transform.e * dst_height)
            bounds_latlon = {
                "west": min(left, right),
                "south": min(bottom, top),
                "east": max(left, right),
                "north": max(bottom, top),
            }
            crs_text = dst_crs
            width = int(dst_width)
            height = int(dst_height)
        else:
            arr = src.read(1).astype(np.float32)
            valid_mask = src.read_masks(1) > 0
            if nodata is not None:
                valid_mask &= arr != nodata
            bounds_latlon = _bounds_to_latlon(src)
            width = int(src.width)
            height = int(src.height)

    min_val, max_val = _array_to_png(arr, valid_mask, image_path)
    return bounds_latlon, crs_text, min_val, max_val, width, height


def upload_dsm(file_path: Path, original_name: str, data_dir: Path) -> DsmOverlay:
    dsm_id = str(uuid.uuid4())
    image_path = data_dir / f"{dsm_id}.png"
    bounds_latlon, crs_text, min_val, max_val, width, height = render_geotiff_overlay(file_path, image_path)

    item = DsmOverlay(
        dsm_id=dsm_id,
        name=original_name,
        path=str(file_path),
        image_path=str(image_path),
        crs=crs_text,
        width=width,
        height=height,
        min_val=min_val,
        max_val=max_val,
        bounds_latlon=bounds_latlon,
    )

    DSM_REGISTRY[dsm_id] = item
    return item


def list_dsms() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in DSM_REGISTRY.values():
        out.append(
            {
                "dsm_id": d.dsm_id,
                "name": d.name,
                "crs": d.crs,
                "width": d.width,
                "height": d.height,
                "min_val": d.min_val,
                "max_val": d.max_val,
                "bounds_latlon": d.bounds_latlon,
            }
        )
    return out


def get_dsm_or_404(dsm_id: str) -> DsmOverlay:
    d = DSM_REGISTRY.get(dsm_id)
    if d is None:
        raise HTTPException(status_code=404, detail="DSM not found")
    return d
