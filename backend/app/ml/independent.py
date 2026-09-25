"""Single-pollutant forecasts. Missing PM10 never becomes a PM2.5 feature."""
import numpy as np
import pandas as pd
from app.ml.model import estimator, regression_metrics


def forecast_pollutant(series, origin, weather=None):
    series = series.dropna().sort_index()
    if series.empty:
        return None
    last = series.index[-1]
    age = int((origin - last).total_seconds() // 3600)
    if age < 0 or age > 6:
        return None
    horizon = 30
    s = series.reindex(pd.date_range(series.index[0], last, freq="h"))
    x = pd.DataFrame({f"lag_{i}": s.shift(i) for i in range(25)})
    x["hour"] = x.index.hour
    if weather is not None:
        x = x.join(weather[["temperature_c", "humidity_pct", "wind_speed_ms", "wind_direction_deg", "pressure_hpa"]])
    y = pd.DataFrame({f"h_{i}": s.shift(-i) for i in range(1, horizon + 1)})
    valid = x.notna().all(axis=1) & y.notna().all(axis=1)
    train_x, train_y = x[valid], y[valid]
    result = {"values": np.repeat(float(s.iloc[-1]), 24), "interval": None,
              "method": "Station persistence (unvalidated)", "metrics": None}
    if len(train_x) < 500 or x.iloc[-1].isna().any():
        return result
    n = len(train_x)
    a, b = int(n * .60), int(n * .80)
    # Purge all target horizons between train, calibration and untouched test.
    cal, test = a + horizon, b + horizon
    if min(b-cal, n-test) < 30:
        return result
    model = estimator()
    model.fit(train_x.iloc[:a], train_y.iloc[:a])
    cal_pred = model.predict(train_x.iloc[cal:b])
    cal_base = np.repeat(train_x.iloc[cal:b]["lag_0"].to_numpy()[:, None], horizon, axis=1)
    # Model choice uses calibration only. Test is not used to select the winner.
    use_tree = np.mean(abs(cal_pred-train_y.iloc[cal:b].to_numpy())) < np.mean(abs(cal_base-train_y.iloc[cal:b].to_numpy()))
    pred = model.predict(train_x.iloc[test:])
    base = np.repeat(train_x.iloc[test:]["lag_0"].to_numpy()[:, None], horizon, axis=1)
    spread = np.quantile(abs(train_y.iloc[cal:b].to_numpy() - (cal_pred if use_tree else cal_base)), .9, axis=0)
    values = model.predict(x.tail(1))[0] if use_tree else np.repeat(float(s.iloc[-1]), horizon)
    return {"values": np.maximum(0, values[age:age+24]),
            "interval": spread[age:age+24],
            "method": ("Independent station + weather Extra Trees" if weather is not None else "Independent station Extra Trees") if use_tree else "Station persistence (calibration-selected)",
            "metrics": {"model": regression_metrics(train_y.iloc[test:], pred),
                        "persistence": regression_metrics(train_y.iloc[test:], base),
                        "train_rows": a, "calibration_rows": b-cal, "test_rows": n-test,
                        "purge_hours": horizon}}
