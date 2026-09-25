"""Observation-first, per-pollutant forecasts with explicit CAMS fallback.

CAMS is model output, never a training label or an observed concentration.
"""
from datetime import timedelta
import json
import httpx
import pandas as pd
from app.config import get_settings
from app.data.openaq import DataUnavailable, request, provider_timeout, sensor_hours, valid_value, weather as collect_weather
from app.ml.independent import forecast_pollutant
from app.data.airnow import collect_airnow


def resilient_dataset(location, failure):
    now = pd.Timestamp.now(tz="UTC").floor("h")
    stations = failure.stations or []
    warnings = [str(failure), "Regional model estimates are not station measurements. Screening alerts are provisional; verify locally before operational decisions."]
    airnow_history = {}
    try:
        extra, airnow_history, airnow_status = collect_airnow(location)
        stations = [*stations, *extra]
        warnings.append(airnow_status)
    except DataUnavailable as exc:
        warnings.append(str(exc))
    with httpx.Client(timeout=provider_timeout()) as client:
        try:
            aq = request(client, "https://air-quality-api.open-meteo.com/v1/air-quality", params={
                "latitude": location.latitude, "longitude": location.longitude,
                "hourly": "pm2_5,pm10", "forecast_days": 3, "timezone": "UTC", "domains": "cams_global"})
            met = request(client, "https://api.open-meteo.com/v1/forecast", params={
                "latitude": location.latitude, "longitude": location.longitude,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure",
                "wind_speed_unit": "ms", "forecast_days": 3, "timezone": "UTC"})
        except DataUnavailable as exc:
            raise DataUnavailable(f"Station forecast unavailable; regional fallback also failed: {exc}", stations=stations) from None
    hourly = pd.DataFrame(aq.get("hourly", {})).rename(columns={"time": "timestamp", "pm2_5": "pm25"})
    if not {"timestamp", "pm25", "pm10"}.issubset(hourly):
        raise DataUnavailable("CAMS returned no usable particulate forecast.", stations=stations)
    hourly["timestamp"] = pd.to_datetime(hourly.timestamp, utc=True)
    hourly = hourly.set_index("timestamp")
    window = hourly.reindex(pd.date_range(now, periods=25, freq="h"))
    if window[["pm25", "pm10"]].isna().any().any() or not all(valid_value(v) for v in window[["pm25", "pm10"]].to_numpy().ravel()):
        raise DataUnavailable("CAMS does not cover the current hour and next 24 hours.", stations=stations)
    names = {"temperature_2m": "temperature_c", "relative_humidity_2m": "humidity_pct",
             "wind_speed_10m": "wind_speed_ms", "wind_direction_10m": "wind_direction_deg", "surface_pressure": "pressure_hpa"}
    weather = pd.DataFrame(met.get("hourly", {})).rename(columns={"time": "timestamp", **names})
    if not {"timestamp", *names.values()}.issubset(weather):
        raise DataUnavailable("Weather provider returned incomplete current conditions.", stations=stations)
    weather["timestamp"] = pd.to_datetime(weather.timestamp, utc=True)
    weather = weather.set_index("timestamp").reindex([now])
    if weather.isna().any().any():
        raise DataUnavailable("Current weather model hour unavailable.", stations=stations)
    current = {"timestamp": now, **weather.iloc[0].to_dict()}
    prediction = {"metrics": None, "importance": [], "drivers": [],
                  "method": "Independent pollutant forecasts + CAMS regional fallback",
                  "note": "Each pollutant uses its own station history where available. Trees are selected against persistence on calibration data, with a 30-hour purge and untouched test set. Otherwise CAMS supplies a regional forecast. CAMS has no local accuracy score or calibrated interval here."}
    provenance = {}
    observed_history = {}
    training_weather = None
    if any(s["readings"] for s in stations):
        try:
            with httpx.Client(timeout=provider_timeout()) as client:
                training_weather = collect_weather(client, location, now-timedelta(days=45), now)
        except DataUnavailable as exc:
            warnings.append(f"Weather history unavailable; independent forecast may use pollution lags only: {exc}")
    for p, interval in [("pm25", "interval25"), ("pm10", "interval10")]:
        current[p] = float(window.iloc[0][p])
        prediction[p] = window[p].iloc[1:].to_numpy()
        prediction[interval] = None
        provenance[p] = {"current_kind": "regional model estimate", "current_at": now.isoformat(),
                         "current_source": "CAMS Global via Open-Meteo", "forecast_method": "CAMS Global regional forecast",
                         "station": None, "metrics": None}
        available = [s for s in stations if p in s["readings"]]
        if not available:
            continue
        selected = min(available, key=lambda s: (s.get("distance_km", 0), s["readings"][p]["age_hours"]))
        reading = selected["readings"][p]
        # Retain actual timestamp: a several-hours-old measurement is not 'now'.
        current[p] = reading["value"]
        selected["selected"] = True
        provenance[p].update(current_kind="station measurement", current_at=reading["observed_at"],
                             current_source=selected["provider"], station=selected["name"])
        provenance[p]["distance_km"] = selected.get("distance_km")
        try:
            if selected.get("source_api") == "airnow":
                series = airnow_history[reading["sensor_id"]]
            else:
                with httpx.Client(timeout=provider_timeout(), headers={"X-API-Key": get_settings().openaq_api_key.strip()}) as client:
                    series = sensor_hours(client, reading["sensor_id"], now-timedelta(days=45), now)
            observed_history[p] = series
            trained = forecast_pollutant(series, now, training_weather)
            if trained:
                prediction[p] = trained["values"]
                prediction[interval] = trained["interval"]
                provenance[p].update(forecast_method=trained["method"], metrics=trained["metrics"])
        except DataUnavailable as exc:
            warnings.append(f"{p} history: {exc}; forecast uses CAMS.")
    if current["pm25"] > current["pm10"]:
        warnings.append("PM2.5 exceeds PM10 across these sources/times. This is a comparability flag, not a negative coarse-particle estimate; no ratio correction was applied.")
    prediction["note"] += " Sources can represent different locations and times; pollutant ratios and source attribution are not inferred."
    history = pd.DataFrame(observed_history).reindex(columns=["pm25", "pm10"])
    history.index.name = "timestamp"
    history.index = pd.DatetimeIndex(history.index, tz="UTC") if history.empty else history.index
    # Persist measured history separately from model output for future training.
    if not history.empty:
        history.to_csv(get_settings().processed_dir / f"{location.id}-independent-observations.csv")
    record = {"retrieved_at": pd.Timestamp.now(tz="UTC").isoformat(), "origin": now.isoformat(),
              "city": location.id, "provenance": provenance, "regional_model": aq,
              "forecast": {p: list(map(float, prediction[p])) for p in ["pm25", "pm10"]}}
    archive = get_settings().processed_dir / "forecast_runs"
    archive.mkdir(exist_ok=True)
    run_stamp = pd.Timestamp(record["retrieved_at"]).strftime('%Y%m%dT%H%M%S%f')
    (archive / f"{location.id}-{run_stamp}.json").write_text(json.dumps(record), encoding="utf-8")
    return {"frame": pd.DataFrame([current]), "prediction": prediction, "provenance": provenance,
            "observed_history": history.reset_index(), "source": "OpenAQ / AirNow observations / CAMS Global forecasts via Open-Meteo",
            "mode": "live", "stations": stations, "station": None, "coverage_pct": 0,
            "collected_at": record["retrieved_at"], "warnings": warnings,
            "quality": "regional_model" if all(x["current_kind"] == "regional model estimate" for x in provenance.values()) else "mixed_sources"}
