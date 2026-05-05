from __future__ import annotations

import math
import random
from dataclasses import dataclass

SIGMA = 5.67051e-8


@dataclass
class HumanParams:
    abs_k: float = 0.70
    abs_l: float = 0.97
    f_side: float = 0.22
    f_up: float = 0.06
    f_cyl: float = 0.28


@dataclass
class SurfaceParams:
    albedo_ground: float = 0.20
    albedo_wall: float = 0.25
    emiss_ground: float = 0.95
    emiss_wall: float = 0.90
    vegetation_transmissivity: float = 0.30


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _prata_sky_emissivity(ta_c: float, rh_pct: float) -> float:
    ea = 6.107 * (10 ** ((7.5 * ta_c) / (237.3 + ta_c))) * (rh_pct / 100.0)
    m = 46.5 * (ea / (ta_c + 273.15))
    esky = 1.0 - (1.0 + m) * math.exp(-math.sqrt(1.2 + 3.0 * m))
    return _clamp(esky, 0.6, 1.0)


def _stable_noise(i: int, j: int, seed: int) -> float:
    # Deterministic pseudo-noise for procedural urban morphology.
    rng = random.Random((seed * 73856093) ^ (i * 19349663) ^ (j * 83492791))
    return rng.random()


def _cell_environment(i: int, j: int, nx: int, ny: int, solar_altitude_deg: float, seed: int) -> tuple[float, float]:
    n0 = _stable_noise(i, j, seed)
    n1 = _stable_noise(i + 11, j + 17, seed)

    # Building density in [0, 1]; center tends denser than outskirts.
    dx = (i - nx / 2) / max(1.0, nx / 2)
    dy = (j - ny / 2) / max(1.0, ny / 2)
    center_density = _clamp(1.0 - 0.8 * math.sqrt(dx * dx + dy * dy), 0.1, 1.0)
    building_density = _clamp(0.45 * center_density + 0.55 * n0, 0.0, 1.0)

    # Sky-view factor decreases with density.
    svf = _clamp(0.15 + 0.8 * (1.0 - building_density), 0.08, 0.97)

    # Shade fraction increases with low sun + density + canopy signal.
    sun_height_factor = _clamp(math.sin(math.radians(max(solar_altitude_deg, 0.0))), 0.0, 1.0)
    canopy = _clamp(0.15 + 0.65 * n1, 0.0, 1.0)
    shade_fraction = _clamp((1.0 - sun_height_factor) * 0.55 + building_density * 0.30 + canopy * 0.20, 0.0, 1.0)

    return svf, shade_fraction


def _blend_dem_environment(
    svf_base: float,
    shade_base: float,
    solar_altitude_deg: float,
    dem_proxy: dict | None,
) -> tuple[float, float]:
    if dem_proxy is None:
        return svf_base, shade_base

    slope_norm = float(dem_proxy.get("slope_norm", 0.0))
    rough_norm = float(dem_proxy.get("roughness_norm", 0.0))

    sun_height_factor = _clamp(math.sin(math.radians(max(solar_altitude_deg, 0.0))), 0.0, 1.0)

    # Terrain-driven proxies: steeper and rougher terrain lowers openness and increases shading tendency.
    svf_dem = _clamp(0.92 - 0.55 * slope_norm - 0.25 * rough_norm, 0.08, 0.98)
    shade_dem = _clamp((1.0 - sun_height_factor) * (0.35 + 0.45 * slope_norm) + 0.25 * rough_norm, 0.0, 1.0)

    svf = _clamp(0.65 * svf_dem + 0.35 * svf_base, 0.08, 0.98)
    shade_fraction = _clamp(0.65 * shade_dem + 0.35 * shade_base, 0.0, 1.0)

    return svf, shade_fraction


def _tmrt_for_cell(weather: dict, svf: float, shade_fraction: float, human: HumanParams, surf: SurfaceParams) -> dict:
    ta = float(weather["Ta"])
    rh = float(weather["RH"])
    rad_g = max(0.0, float(weather["radG"]))
    rad_d = max(0.0, float(weather["radD"]))
    rad_i = max(0.0, float(weather["radI"]))
    alt = max(0.0, float(weather["solar_altitude"]))

    sun_exposure = _clamp(1.0 - shade_fraction, 0.0, 1.0)
    sin_alt = math.sin(math.radians(alt))
    cos_alt = math.cos(math.radians(alt))

    d_rad = rad_d * svf

    # SOLWEIG-inspired simplified shortwave balance.
    k_down = rad_i * sun_exposure * sin_alt + d_rad + surf.albedo_wall * (1.0 - svf) * rad_g
    k_up = surf.albedo_ground * k_down

    k_side_i = rad_i * sun_exposure * cos_alt
    # Each cardinal side flux should be a full side value, not quartered.
    k_cardinal = rad_i * sun_exposure * cos_alt + rad_d * (1.0 - 0.4 * svf) + 0.5 * k_up

    # Surface temperature excess proxy above air temperature.
    tg = _clamp(0.014 * rad_g * sun_exposure, 0.0, 18.0)

    ta_k = ta + 273.15
    esky = _prata_sky_emissivity(ta, rh)

    l_down = svf * esky * SIGMA * (ta_k**4) + (1.0 - svf) * surf.emiss_wall * SIGMA * ((ta_k + 0.6 * tg) ** 4)
    l_up = surf.emiss_ground * SIGMA * ((ta_k + tg) ** 4)

    # Each cardinal longwave side receives full side exposure in the angular sum.
    l_cardinal = (1.0 - svf) * surf.emiss_wall * SIGMA * ((ta_k + tg) ** 4) + svf * esky * SIGMA * (ta_k**4)

    sstr = human.abs_k * (
        k_side_i * human.f_cyl + (k_down + k_up) * human.f_up + (4.0 * k_cardinal) * human.f_side
    ) + human.abs_l * ((l_down + l_up) * human.f_up + (4.0 * l_cardinal) * human.f_side)

    tmrt = (sstr / (human.abs_l * SIGMA)) ** 0.25 - 273.2

    return {
        "tmrt": tmrt,
        "svf": svf,
        "shade_fraction": shade_fraction,
        "kdown": k_down,
        "kup": k_up,
        "ldown": l_down,
        "lup": l_up,
    }


def generate_tmrt_grid_geojson(
    lat: float,
    lon: float,
    weather: dict,
    grid_size: int = 40,
    span_m: float = 1200.0,
    human: HumanParams | None = None,
    surf: SurfaceParams | None = None,
    dem_sampler=None,
    dem_id: str | None = None,
) -> dict:
    human = human or HumanParams()
    surf = surf or SurfaceParams()

    nx = grid_size
    ny = grid_size

    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * math.cos(math.radians(lat))

    dlat = span_m / meters_per_deg_lat
    dlon = span_m / meters_per_deg_lon

    min_lat = lat - dlat / 2.0
    min_lon = lon - dlon / 2.0
    cell_lat = dlat / ny
    cell_lon = dlon / nx

    seed = int(abs(lat * 1000) + abs(lon * 1000))

    features = []
    values = []

    for j in range(ny):
        for i in range(nx):
            lon0 = min_lon + i * cell_lon
            lat0 = min_lat + j * cell_lat
            lon1 = lon0 + cell_lon
            lat1 = lat0 + cell_lat

            center_lon = (lon0 + lon1) / 2.0
            center_lat = (lat0 + lat1) / 2.0

            svf, shade_fraction = _cell_environment(i, j, nx, ny, float(weather["solar_altitude"]), seed)
            dem_proxy = dem_sampler(center_lat, center_lon) if dem_sampler is not None else None
            svf, shade_fraction = _blend_dem_environment(svf, shade_fraction, float(weather["solar_altitude"]), dem_proxy)

            cell = _tmrt_for_cell(weather, svf, shade_fraction, human, surf)
            tmrt = cell["tmrt"]
            values.append(tmrt)

            if dem_proxy is not None:
                cell["elev_m"] = dem_proxy.get("elev_m")
                cell["terrain_slope_norm"] = dem_proxy.get("slope_norm")
                cell["terrain_roughness_norm"] = dem_proxy.get("roughness_norm")

            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [lon0, lat0],
                                [lon1, lat0],
                                [lon1, lat1],
                                [lon0, lat1],
                                [lon0, lat0],
                            ]
                        ],
                    },
                    "properties": {
                        **cell,
                        "i": i,
                        "j": j,
                    },
                }
            )

    vmin = min(values) if values else 0.0
    vmax = max(values) if values else 0.0

    return {
        "type": "FeatureCollection",
        "metadata": {
            "center": {"lat": lat, "lon": lon},
            "grid_size": grid_size,
            "span_m": span_m,
            "tmrt_min": vmin,
            "tmrt_max": vmax,
            "weather_time": weather.get("time"),
            "dem_id": dem_id,
            "dem_enabled": dem_sampler is not None,
            "model": "SOLWEIG-inspired simplified real-time predictor",
            "warning": "This is a fast operational approximation, not a full SOLWEIG radiative transfer solve.",
        },
        "features": features,
    }
