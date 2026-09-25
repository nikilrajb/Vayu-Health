"""Direct AirNow hourly concentrations; AQI/NowCast values are never training labels."""
import math
import os
import uuid
from hashlib import sha256
import httpx
import pandas as pd
from app.config import get_settings
from app.data.openaq import DataUnavailable, distance_km, valid_value, provider_timeout


def parse_rows(rows, location, now):
    stations, histories = {}, {}
    for row in rows:
        p = {"PM2.5": "pm25", "PM25": "pm25", "PM10": "pm10"}.get(row.get("Parameter"))
        value = row.get("RawConcentration")
        if not p or str(row.get("Unit", "")).upper() != "UG/M3" or not valid_value(value):
            continue
        try:
            lat, lon = float(row["Latitude"]), float(row["Longitude"])
            stamp = pd.Timestamp(row["UTC"])
            stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
            distance = distance_km(location.latitude, location.longitude, lat, lon)
            if not math.isfinite(distance) or distance > 125 or not 0 <= (now-stamp).total_seconds() <= 86400:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        site = str(row.get("IntlAQSCode") or row.get("FullAQSCode") or "")
        if not site:
            continue
        sid = "airnow-" + site
        station = stations.setdefault(sid, {"id": sid, "name": row.get("SiteName") or site,
            "latitude": lat, "longitude": lon, "distance_km": round(distance, 1),
            "provider": "AirNow · " + str(row.get("AgencyName") or "contributor"),
            "source_api": "airnow", "readings": {}, "selected": False})
        sensor = sid + "-" + p
        histories.setdefault(sensor, []).append({"timestamp": stamp, "value": value})
        old = station["readings"].get(p)
        if old is None or stamp > pd.Timestamp(old["observed_at"]):
            station["readings"][p] = {"value": value, "observed_at": stamp.isoformat(),
                "age_hours": round((now-stamp).total_seconds()/3600, 1), "sensor_id": sensor}
    series = {sid: pd.DataFrame(rows).groupby("timestamp").value.mean().sort_index() for sid, rows in histories.items()}
    return list(stations.values()), series


def collect_airnow(location):
    key = get_settings().airnow_api_key.strip()
    if not key:
        return [], {}, "AirNow key is not configured."
    now = pd.Timestamp.now(tz="UTC")
    dy = 125/110.5
    dx = 125/(110.5*math.cos(math.radians(location.latitude)))
    bbox = f"{location.longitude-dx},{location.latitude-dy},{location.longitude+dx},{location.latitude+dy}"
    params = {"startDate": (now-pd.Timedelta(hours=24)).strftime("%Y-%m-%dT%H"),
              "endDate": now.strftime("%Y-%m-%dT%H"), "parameters": "PM25,PM10",
              "BBOX": bbox, "dataType": "C", "format": "application/json", "verbose": 1,
              "includerawconcentrations": 1, "monitorType": 0, "API_KEY": key}
    # Never render request URLs/exceptions: AirNow requires a query-string key.
    try:
        with httpx.Client(timeout=provider_timeout()) as client:
            response = client.get("https://www.airnowapi.org/aq/data/", params=params)
        if response.status_code != 200:
            raise DataUnavailable(f"AirNow returned HTTP {response.status_code}; existing sources remain available.")
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError()
    except (httpx.RequestError, ValueError):
        raise DataUnavailable("AirNow could not return usable observations; existing sources remain available.") from None
    stations, series = parse_rows(rows, location, now)
    folder = get_settings().processed_dir / "airnow"
    folder.mkdir(exist_ok=True)
    for sid, values in series.items():
        path = folder / (sha256(sid.encode()).hexdigest() + ".csv")
        if path.exists():
            previous = pd.read_csv(path)
            previous["timestamp"] = pd.to_datetime(previous.timestamp, utc=True)
            values = pd.concat([previous.set_index("timestamp").value, values])
            values = values[~values.index.duplicated(keep="last")].sort_index()
        values = values[values.index >= now-pd.Timedelta(days=45)]
        temp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        values.rename("value").rename_axis("timestamp").to_csv(temp)
        os.replace(temp, path)
        series[sid] = values
    return stations, series, f"AirNow: {len(stations)} sites with raw PM concentrations within 125 km in the last 24 hours."
