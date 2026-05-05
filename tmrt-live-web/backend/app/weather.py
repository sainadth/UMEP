from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from astral import LocationInfo
from astral.sun import azimuth as sun_azimuth
from astral.sun import elevation as sun_elevation

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_live_weather(lat: float, lon: float) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "shortwave_radiation",
                "direct_radiation",
                "diffuse_radiation",
                "surface_pressure",
            ]
        ),
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    current = payload.get("current", {})
    current_units = payload.get("current_units", {})
    tz_name = payload.get("timezone", "UTC")

    # Open-Meteo timestamp is local time with timezone in payload.
    current_time = datetime.fromisoformat(current.get("time"))

    location = LocationInfo(name="target", region="target", timezone=tz_name, latitude=lat, longitude=lon)
    solar_altitude = float(sun_elevation(location.observer, current_time))
    solar_azimuth = float(sun_azimuth(location.observer, current_time))

    return {
        "source": "open-meteo",
        "timezone": tz_name,
        "time": current.get("time"),
        "Ta": float(current.get("temperature_2m", 0.0)),
        "RH": float(current.get("relative_humidity_2m", 0.0)),
        "Ws": float(current.get("wind_speed_10m", 0.0)),
        "radG": float(current.get("shortwave_radiation", 0.0)),
        "radI": float(current.get("direct_radiation", 0.0)),
        "radD": float(current.get("diffuse_radiation", 0.0)),
        "P": float(current.get("surface_pressure", 1013.25)),
        "solar_altitude": solar_altitude,
        "solar_azimuth": solar_azimuth,
        "units": {
            "Ta": current_units.get("temperature_2m", "degC"),
            "RH": current_units.get("relative_humidity_2m", "%"),
            "Ws": current_units.get("wind_speed_10m", "m/s"),
            "radG": current_units.get("shortwave_radiation", "W/m^2"),
            "radI": current_units.get("direct_radiation", "W/m^2"),
            "radD": current_units.get("diffuse_radiation", "W/m^2"),
            "P": current_units.get("surface_pressure", "hPa"),
            "solar_altitude": "deg",
            "solar_azimuth": "deg",
        },
    }
