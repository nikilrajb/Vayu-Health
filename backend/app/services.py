from datetime import timedelta
import pandas as pd
from app.alerts import build_alerts
from app.aqi import aqi_from_pm
from app.catalog import CITIES, get_location
from app.data.openaq import collect
from app.data.synthetic import extend_to_now, load_city_series
from app.ml.model import forecast_model


def list_locations():
    return list(CITIES.values())


def dataset(city_id, mode="live"):
    location = get_location(city_id)
    if mode == "live":
        return collect(location)
    frame = extend_to_now(load_city_series(location.id), location.id)
    return {
        "frame": frame,
        "source": "Synthetic demonstration data",
        "mode": "demo",
        "stations": [],
        "station": None,
        "coverage_pct": 100,
        "collected_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "warnings": [
            "All observations, weather, forecasts and evaluation scores in demo mode are based on synthetic data. They do not describe real conditions."
        ],
    }


def city_snapshot(city_id, mode="live"):
    location = get_location(city_id)
    ds = dataset(city_id, mode)
    frame = ds["frame"]
    prediction = forecast_model(location.id, frame, mode)
    last = frame.dropna().iloc[-1]
    now = pd.Timestamp(last.timestamp).to_pydatetime()
    forecast = []
    for h, (pm25, pm10) in enumerate(zip(prediction["pm25"], prediction["pm10"])):
        aqi, category, dominant = aqi_from_pm(pm25, pm10)
        row = {
            "timestamp": now + timedelta(hours=h + 1),
            "horizon_h": h + 1,
            "pm25": round(float(pm25), 1),
            "pm10": round(float(pm10), 1),
            "aqi": aqi,
            "aqi_category": category,
            "dominant_pollutant": dominant,
        }
        for pollutant, band in [("pm25", "interval25"), ("pm10", "interval10")]:
            spread = prediction[band]
            row[f"{pollutant}_lower"] = (
                round(max(0, row[pollutant] - float(spread[h])), 1)
                if spread is not None
                else None
            )
            row[f"{pollutant}_upper"] = (
                round(row[pollutant] + float(spread[h]), 1)
                if spread is not None
                else None
            )
        forecast.append(row)
    aqi, category, dominant = aqi_from_pm(last.pm25, last.pm10)
    peak = max(forecast, key=lambda r: r["aqi"])
    priority = (
        "high" if peak["aqi"] >= 151 else "medium" if peak["aqi"] >= 101 else "low"
    )
    actions = [
        "Review emission-control equipment and maintenance logs",
        "Increase dust control and inspect covered material handling",
        "Review whether high-emission operations can be rescheduled before the forecast peak",
    ]
    interventions = [
        {
            "id": f"{city_id}-{i}",
            "zone": zone,
            "action": actions[i % len(actions)],
            "rationale": f"Forecast peak risk index {peak['aqi']}. Listed industrial area for operator review; source contribution and downwind exposure have not been established.",
            "compliance_priority": priority,
            "window_hours": peak["horizon_h"],
        }
        for i, zone in enumerate(location.industrial_zones)
    ]
    recent = frame.tail(72).copy().replace({float("nan"): None})
    return {
        "location": location,
        "observed_at": now,
        "pm25": round(float(last.pm25), 1),
        "pm10": round(float(last.pm10), 1),
        "aqi": aqi,
        "aqi_category": category,
        "dominant_pollutant": dominant,
        "weather": {
            k: round(float(last[k]), 1)
            for k in [
                "temperature_c",
                "humidity_pct",
                "wind_speed_ms",
                "wind_direction_deg",
                "pressure_hpa",
            ]
        },
        "data_source": ds["source"],
        "mode": mode,
        "coverage_pct": ds["coverage_pct"],
        "collected_at": ds["collected_at"],
        "warnings": ds["warnings"],
        "stations": ds["stations"],
        "station": ds["station"],
        "forecast": forecast,
        "alerts": build_alerts(location, now, forecast),
        "interventions": interventions,
        "history": recent.to_dict(orient="records"),
        "model": {
            k: prediction[k]
            for k in ["method", "metrics", "importance", "drivers", "note"]
        },
        "aqi_method": "US EPA 2024 PM concentration breakpoints applied to hourly values as a screening risk index. Not an official daily AQI or NowCast; not India's CPCB AQI.",
        "impact_note": "No measured emission reductions, population protection or industrial compliance outcomes are claimed.",
    }


def history(city_id, hours=72, mode="live"):
    return dataset(city_id, mode)["frame"].tail(hours)
