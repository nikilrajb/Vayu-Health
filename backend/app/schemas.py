from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Pollutant = Literal["pm25", "pm10"]
AqiCategory = Literal[
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]
AlertSeverity = Literal["info", "watch", "warning", "emergency"]


class Location(BaseModel):
    id: str
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    industrial_zones: list[str]


class HourlyObservation(BaseModel):
    timestamp: datetime
    pm25: float
    pm10: float
    temperature_c: float
    humidity_pct: float
    wind_speed_ms: float
    wind_direction_deg: float
    pressure_hpa: float


class ForecastHour(BaseModel):
    timestamp: datetime
    horizon_h: int
    pm25: float
    pm10: float
    aqi: int
    aqi_category: AqiCategory
    dominant_pollutant: Pollutant


class HealthAlert(BaseModel):
    id: str
    severity: AlertSeverity
    title: str
    message: str
    aqi: int
    aqi_category: AqiCategory
    valid_from: datetime
    valid_to: datetime
    populations: list[str]
