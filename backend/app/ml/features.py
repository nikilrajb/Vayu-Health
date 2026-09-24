from __future__ import annotations

import pandas as pd

LAGS = (1, 3, 6, 12, 24)
ROLLS = (6, 12, 24)
HORIZONS = 24
FEATURE_COLUMNS = [
    "hour",
    "dow",
    "month",
    "is_weekend",
    "pm25",
    "pm10",
    "temperature_c",
    "humidity_pct",
    "wind_speed_ms",
    "wind_direction_deg",
    "pressure_hpa",
    *[f"pm25_lag_{k}" for k in LAGS],
    *[f"pm10_lag_{k}" for k in LAGS],
    *[f"pm25_roll_{k}" for k in ROLLS],
    *[f"pm10_roll_{k}" for k in ROLLS],
]


def add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    ts = pd.to_datetime(out["timestamp"], utc=True)
    out["hour"] = ts.dt.hour
    out["dow"] = ts.dt.dayofweek
    out["month"] = ts.dt.month
    out["is_weekend"] = (out["dow"] >= 5).astype(int)
    return out


def add_lags(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values("timestamp").copy()
    for col in ("pm25", "pm10"):
        for lag in LAGS:
            out[f"{col}_lag_{lag}"] = out[col].shift(lag)
        for win in ROLLS:
            out[f"{col}_roll_{win}"] = out[col].shift(1).rolling(win).mean()
    return out


def build_supervised(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feat = add_lags(add_time_features(frame))
    for h in range(1, HORIZONS + 1):
        feat[f"y_pm25_h{h}"] = feat["pm25"].shift(-h)
        feat[f"y_pm10_h{h}"] = feat["pm10"].shift(-h)
    feat = feat.dropna().reset_index(drop=True)
    x = feat[FEATURE_COLUMNS]
    y25 = feat[[f"y_pm25_h{h}" for h in range(1, HORIZONS + 1)]]
    y10 = feat[[f"y_pm10_h{h}" for h in range(1, HORIZONS + 1)]]
    return x, y25, y10


def latest_feature_row(frame: pd.DataFrame) -> pd.DataFrame:
    feat = add_lags(add_time_features(frame))
    row = feat.dropna(subset=FEATURE_COLUMNS).iloc[[-1]][FEATURE_COLUMNS]
    return row
