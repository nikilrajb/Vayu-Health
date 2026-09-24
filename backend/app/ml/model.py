"""Direct 24-horizon trees with purged chronological evaluation."""

from hashlib import sha256
from threading import Lock
import joblib
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from app.config import get_settings
from app.ml.features import (
    FEATURE_COLUMNS,
    HORIZONS,
    build_supervised,
    latest_feature_row,
)

_lock = Lock()


def estimator():
    return ExtraTreesRegressor(
        n_estimators=64, max_depth=14, min_samples_leaf=3, random_state=42, n_jobs=2
    )


def regression_metrics(actual, predicted):
    return {
        "mae": round(float(mean_absolute_error(actual, predicted)), 2),
        "rmse": round(float(np.sqrt(mean_squared_error(actual, predicted))), 2),
        "r2": round(float(r2_score(actual, predicted)), 3),
    }


def forecast_model(city_id, frame, mode):
    complete = frame.dropna().iloc[-1]
    persistence = {
        "pm25": np.repeat(float(complete.pm25), 24),
        "pm10": np.repeat(float(complete.pm10), 24),
        "metrics": None,
        "importance": [],
        "drivers": [],
        "method": "Persistence baseline",
        "interval25": None,
        "interval10": None,
        "note": "Insufficient continuous history for a validated tree model. Each horizon repeats the latest complete concentration; uncertainty is not calibrated.",
    }
    x, y25, y10 = build_supervised(frame)
    if len(x) < 400 or frame.tail(25).isna().any().any():
        return persistence
    latest = latest_feature_row(frame)
    fingerprint = sha256(frame.to_csv(index=False).encode()).hexdigest()[:16]
    path = get_settings().model_dir / f"{city_id}-{mode}-v4-{fingerprint}.joblib"
    with _lock:
        if path.exists():
            bundle = joblib.load(path)
        else:
            train_end, val_end = int(len(x) * 0.65), int(len(x) * 0.82)
            val_start, test_start = train_end + HORIZONS, val_end + HORIZONS
            if min(val_end - val_start, len(x) - test_start) < 24:
                return persistence
            models = [estimator(), estimator()]
            scores, residuals, preds = [], [], []
            for model, target, pollutant in zip(models, [y25, y10], ["pm25", "pm10"]):
                model.fit(x.iloc[:train_end], target.iloc[:train_end])
                validation = model.predict(x.iloc[val_start:val_end])
                residuals.append(
                    np.quantile(
                        np.abs(target.iloc[val_start:val_end].to_numpy() - validation),
                        0.9,
                        axis=0,
                    )
                )
                pred = model.predict(x.iloc[test_start:])
                baseline = np.repeat(
                    x.iloc[test_start:][pollutant].to_numpy()[:, None], 24, axis=1
                )
                scores.append(
                    {
                        "model": regression_metrics(target.iloc[test_start:], pred),
                        "persistence": regression_metrics(
                            target.iloc[test_start:], baseline
                        ),
                    }
                )
                preds.append(pred)
            actual_events = (
                (y25.iloc[test_start:].to_numpy() >= 55.5)
                | (y10.iloc[test_start:].to_numpy() >= 255)
            ).ravel()
            predicted_events = ((preds[0] >= 55.5) | (preds[1] >= 255)).ravel()
            precision, recall, f1, _ = precision_recall_fscore_support(
                actual_events, predicted_events, average="binary", zero_division=0
            )
            importance = (
                models[0].feature_importances_ + models[1].feature_importances_
            ) / 2
            bundle = {
                "models": models,
                "reference": x.iloc[:train_end].median(),
                "intervals": residuals,
                "importance": sorted(
                    [
                        {"feature": k, "importance": round(float(v) * 100, 2)}
                        for k, v in zip(FEATURE_COLUMNS, importance)
                    ],
                    key=lambda item: -item["importance"],
                )[:6],
                "metrics": {
                    "pm25": scores[0],
                    "pm10": scores[1],
                    "alerts": {
                        "precision": round(float(precision), 3),
                        "recall": round(float(recall), 3),
                        "f1": round(float(f1), 3),
                        "positive_samples": int(actual_events.sum()),
                    },
                    "train_rows": train_end,
                    "validation_rows": val_end - val_start,
                    "test_rows": len(x) - test_start,
                    "gap_hours": HORIZONS,
                    "data_mode": mode,
                },
            }
            joblib.dump(bundle, path)
    predictions = [np.maximum(0, m.predict(latest)[0]) for m in bundle["models"]]
    groups = {
        "Recent particulate history": [
            c for c in FEATURE_COLUMNS if c.startswith("pm")
        ],
        "Wind conditions": ["wind_speed_ms", "wind_direction_deg"],
        "Temperature and humidity": ["temperature_c", "humidity_pct"],
        "Time and season": ["hour", "dow", "month", "is_weekend"],
        "Surface pressure": ["pressure_hpa"],
    }
    drivers = []
    for label, columns in groups.items():
        reference_row = latest.copy()
        for column in columns:
            reference_row[column] = bundle["reference"][column]
        deltas = [
            round(float(pred.mean() - model.predict(reference_row)[0].mean()), 2)
            for pred, model in zip(predictions, bundle["models"])
        ]
        drivers.append(
            {"label": label, "pm25_delta": deltas[0], "pm10_delta": deltas[1]}
        )
    return {
        "pm25": predictions[0],
        "pm10": predictions[1],
        "method": "Extra Trees · direct 24-hour forecast",
        "metrics": bundle["metrics"],
        "importance": bundle["importance"],
        "drivers": drivers,
        "interval25": bundle["intervals"][0],
        "interval10": bundle["intervals"][1],
        "note": "Earlier 65% training / 17% calibration / 18% test, with 24-hour gaps. Bands use the 90th percentile of calibration absolute errors per horizon; future coverage is not guaranteed. Importance is global and non-causal.",
    }
