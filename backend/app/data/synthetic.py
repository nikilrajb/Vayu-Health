"""Synthetic + cached ambient series for demo and offline training.

Used only when the caller explicitly selects demo mode. Live observations
are never mixed into these synthetic series.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path

import numpy as np
import pandas as pd

from app.catalog import CITY_CLIMATE, CITIES
from app.config import get_settings

HOURS = 24 * 90  # 90-day hourly history


def _rng(city_id: str) -> np.random.Generator:
    seed = int(md5(city_id.encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def synthesize_city(
    city_id: str, hours: int = HOURS, end: datetime | None = None
) -> pd.DataFrame:
    loc = CITIES[city_id]
    # Explicit demo defaults only; these are never used by live collection.
    climate = CITY_CLIMATE.get(city_id, CITY_CLIMATE["delhi"])
    end = end or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    index = pd.date_range(end=end, periods=hours, freq="h", tz="UTC")
    rng = _rng(city_id)
    t = np.arange(hours)

    hour = index.hour.to_numpy()
    doy = index.dayofyear.to_numpy()

    diurnal = 0.35 * np.sin((hour - 8) / 24 * 2 * np.pi) + 0.25 * np.sin(
        (hour - 18) / 24 * 2 * np.pi
    )
    seasonal = np.sin((doy - 20) / 365 * 2 * np.pi) * 0.45
    weekend = np.where(index.dayofweek.to_numpy() >= 5, -0.12, 0.0)

    noise = rng.normal(0, 0.12, hours)
    spikes = np.zeros(hours)
    for _ in range(hours // 80):
        i = int(rng.integers(12, hours - 12))
        width = int(rng.integers(3, 10))
        mag = rng.uniform(0.4, 1.3)
        spikes[i : i + width] += mag * np.hanning(width)

    intensity = np.clip(1.0 + diurnal + seasonal + weekend + noise + spikes, 0.15, 4.0)
    pm25 = climate["pm25_base"] * intensity + rng.normal(
        0, climate["pm25_base"] * 0.04, hours
    )
    pm10 = (
        climate["pm10_base"] * intensity * rng.uniform(0.95, 1.12, hours) + pm25 * 0.15
    )

    temp = (
        climate["temp_mean"]
        + 7 * np.sin((hour - 14) / 24 * 2 * np.pi)
        + climate["season_amp"] * 0.15 * np.sin((doy - 200) / 365 * 2 * np.pi)
        + rng.normal(0, 1.2, hours)
    )
    humidity = np.clip(
        climate["humidity"] - 8 * diurnal + rng.normal(0, 4, hours),
        15,
        98,
    )
    wind = np.clip(
        climate["wind"] + rng.normal(0, 0.8, hours) + 0.6 * np.sin(t / 18), 0.2, 12
    )
    wind_dir = (
        rng.normal(220 if loc.longitude > 0 else 270, 40, hours) + t * 0.4
    ) % 360
    pressure = climate["pressure"] + rng.normal(0, 3.5, hours) - 4 * seasonal

    frame = pd.DataFrame(
        {
            "timestamp": index,
            "city_id": city_id,
            "pm25": np.clip(pm25, 1, 650),
            "pm10": np.clip(pm10, 2, 800),
            "temperature_c": temp,
            "humidity_pct": humidity,
            "wind_speed_ms": wind,
            "wind_direction_deg": wind_dir,
            "pressure_hpa": pressure,
        }
    )
    return frame


def synthesize_all() -> pd.DataFrame:
    return pd.concat([synthesize_city(cid) for cid in CITIES], ignore_index=True)


def sample_csv_path(city_id: str) -> Path:
    return get_settings().sample_dir / f"{city_id}_hourly.csv"


def ensure_sample_files() -> None:
    settings = get_settings()
    settings.sample_dir.mkdir(parents=True, exist_ok=True)
    for city_id in CITIES:
        path = sample_csv_path(city_id)
        if not path.exists():
            synthesize_city(city_id).to_csv(path, index=False)


def load_city_series(city_id: str) -> pd.DataFrame:
    ensure_sample_files()
    path = sample_csv_path(city_id)
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.sort_values("timestamp").reset_index(drop=True)


def extend_to_now(frame: pd.DataFrame, city_id: str) -> pd.DataFrame:
    """Keep the last 90 days ending at the current UTC hour."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    last = frame["timestamp"].max().to_pydatetime()
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last >= now:
        cutoff = now - timedelta(hours=HOURS - 1)
        return frame[frame["timestamp"] >= cutoff].copy()

    gap = int((now - last).total_seconds() // 3600)
    extra = synthesize_city(city_id, hours=min(gap, HOURS), end=now)
    merged = pd.concat([frame, extra], ignore_index=True)
    merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    cutoff = now - timedelta(hours=HOURS - 1)
    return merged[merged["timestamp"] >= cutoff].reset_index(drop=True)
