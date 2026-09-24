"""EPA 2024 PM breakpoints. Hourly output is a risk proxy, not a NowCast."""

from __future__ import annotations

from typing import Literal
from math import floor

Pollutant = Literal["pm25", "pm10"]

# (C_low, C_high, I_low, I_high)
PM25_BREAKPOINTS: list[tuple[float, float, int, int]] = [
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
]

PM10_BREAKPOINTS: list[tuple[float, float, int, int]] = [
    (0.0, 54.0, 0, 50),
    (55.0, 154.0, 51, 100),
    (155.0, 254.0, 101, 150),
    (255.0, 354.0, 151, 200),
    (355.0, 424.0, 201, 300),
    (425.0, 504.0, 301, 400),
    (505.0, 604.0, 401, 500),
]

CATEGORY_BY_AQI: list[tuple[int, str]] = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (500, "Hazardous"),
]


def _sub_index(conc: float, table: list[tuple[float, float, int, int]]) -> int:
    c = max(0.0, float(conc))
    for c_lo, c_hi, i_lo, i_hi in table:
        if c <= c_hi or table[-1] == (c_lo, c_hi, i_lo, i_hi):
            if c > c_hi:
                c = c_hi
            if c < c_lo:
                c = c_lo
            return int(round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo))
    return 500


def aqi_from_pm(pm25: float, pm10: float) -> tuple[int, str, Pollutant]:
    i25 = _sub_index(floor(max(0, pm25) * 10) / 10, PM25_BREAKPOINTS)
    i10 = _sub_index(floor(max(0, pm10)), PM10_BREAKPOINTS)
    aqi = max(i25, i10)
    dominant: Pollutant = "pm25" if i25 >= i10 else "pm10"
    category = "Hazardous"
    for ceiling, label in CATEGORY_BY_AQI:
        if aqi <= ceiling:
            category = label
            break
    return min(aqi, 500), category, dominant
