"""OpenAQ v3 ingestion with bounded pagination, provenance and explicit failures."""

from __future__ import annotations

import math
from numbers import Real
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx
import pandas as pd

from app.config import get_settings

BASE = "https://api.openaq.org/v3"
SEARCH_RADIUS_KM = 125
_cache: dict = {}
_lock = Lock()


class DataUnavailable(RuntimeError):
    def __init__(self, message, stations=None):
        super().__init__(message)
        self.stations = stations


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b-a, math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def discover_locations(client, location):
    # OpenAQ caps its radius parameter at 25 km. Use its supported bbox query
    # then apply an exact spherical distance filter to obtain a 125 km circle.
    angular = SEARCH_RADIUS_KM / 6371.0088
    lat_delta = math.degrees(angular)
    lon_delta = math.degrees(math.asin(min(1, math.sin(angular)/math.cos(math.radians(location.latitude)))))
    bounds = [location.longitude-lon_delta, location.latitude-lat_delta,
              location.longitude+lon_delta, location.latitude+lat_delta]
    # Round outward to the API's four-decimal precision.
    bounds = [math.floor(v*10000)/10000 if i<2 else math.ceil(v*10000)/10000 for i,v in enumerate(bounds)]
    rows = {}
    for page in range(1, 6):
        payload = request(client, f"{BASE}/locations", params={
            "bbox": ",".join(f"{v:.4f}" for v in bounds), "limit": 1000, "page": page})
        batch = payload.get("results") or []
        for loc in batch:
            coords = loc.get("coordinates") or {}
            if coords.get("latitude") is None or coords.get("longitude") is None:
                continue
            distance = distance_km(location.latitude, location.longitude, coords["latitude"], coords["longitude"])
            if distance <= SEARCH_RADIUS_KM:
                rows[loc["id"]] = {**loc, "distance_km": round(distance, 1)}
        if len(batch) < 1000:
            return list(rows.values())
    raise DataUnavailable("Station discovery exceeded its 5,000-location budget. Narrow the search before retrying.")


def request(client, url, **kwargs):
    host = httpx.URL(url).host
    provider = "OpenAQ" if host == "api.openaq.org" else "CAMS air-quality provider" if host == "air-quality-api.open-meteo.com" else "Weather provider"
    retries = getattr(get_settings(), "provider_retries", 1)
    for attempt in range(retries + 1):
        retry = False
        try:
            if host == "api.openaq.org":
                from app.data.quota import pace_openaq
                pace_openaq()
            response = client.get(url, **kwargs)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            return payload
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            detail = {
                401: f"{provider} rejected authentication. Check the server API key and restart the API.",
                403: f"{provider} denied access. Check account permissions or contact the provider.",
                429: f"{provider} rate limit reached. Wait for the quota window to reset before retrying.",
            }.get(code, f"{provider} returned HTTP {code}.")
            retry = code in (502, 503, 504)
        except httpx.ConnectTimeout:
            detail = f"{provider} connection timed out before an HTTP response. Check network access to {host}:443; this does not establish whether the key is valid."
            retry = True
        except httpx.ReadTimeout:
            detail = f"{provider} connected but timed out waiting for response data. Retry later or increase PROVIDER_READ_TIMEOUT_SECONDS on the server."
            retry = True
        except httpx.ProxyError:
            detail = f"{provider} proxy connection failed. Check the approved HTTP_PROXY / HTTPS_PROXY configuration on the API host."
        except httpx.ConnectError:
            detail = f"{provider} connection failed. Check DNS, HTTPS connectivity and certificate trust for {host}."
            retry = True
        except httpx.TimeoutException:
            detail = f"{provider} request timed out. Retry after checking provider availability."
            retry = True
        except httpx.RequestError:
            detail = f"{provider} request failed before a usable response was received."
        except ValueError:
            detail = f"{provider} returned an invalid JSON response."
        if not retry or attempt == retries:
            raise DataUnavailable(detail) from None
        time.sleep(0.5 * (attempt + 1))


def provider_timeout():
    settings = get_settings()
    return httpx.Timeout(
        getattr(settings, "provider_read_timeout_seconds", 25),
        connect=getattr(settings, "provider_connect_timeout_seconds", 8),
    )


def parameter(sensor):
    p = sensor.get("parameter") or {}
    name = str(p.get("name", "")).lower().replace(".", "")
    unit = str(p.get("units", "")).replace("μ", "u").replace("µ", "u").replace("³", "3")
    return name if name in ("pm25", "pm10") and unit == "ug/m3" else None


def valid_value(value):
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def sensor_hours(client, sensor_id, start, end):
    rows = []
    for page in range(1, 7):
        payload = request(
            client,
            f"{BASE}/sensors/{sensor_id}/hours",
            params={
                "datetime_from": start.isoformat(),
                "datetime_to": end.isoformat(),
                "limit": 1000,
                "page": page,
            },
        )
        batch = payload.get("results") or []
        for item in batch:
            coverage = (item.get("coverage") or {}).get("percentCoverage")
            stamp = ((item.get("period") or {}).get("datetimeFrom") or {}).get("utc")
            if (
                stamp
                and valid_value(item.get("value"))
                and (coverage is None or coverage >= 75)
            ):
                rows.append({"timestamp": stamp, "value": item["value"]})
        if len(batch) < 1000:
            break
    if not rows:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz="UTC"))
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True).dt.floor("h")
    return frame.groupby("timestamp").value.mean().sort_index()


def weather(client, location, start, end):
    names = {
        "temperature_2m": "temperature_c",
        "relative_humidity_2m": "humidity_pct",
        "wind_speed_10m": "wind_speed_ms",
        "wind_direction_10m": "wind_direction_deg",
        "surface_pressure": "pressure_hpa",
    }
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "hourly": ",".join(names),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    frames = []
    for url, extra in [
        (
            "https://archive-api.open-meteo.com/v1/archive",
            {
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
            },
        ),
        (
            "https://api.open-meteo.com/v1/forecast",
            {"past_days": 7, "forecast_days": 1},
        ),
    ]:
        payload = request(client, url, params={**params, **extra})
        hourly = payload.get("hourly", {})
        frame = pd.DataFrame(hourly).rename(columns={"time": "timestamp", **names})
        if frame.empty:
            continue
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frames.append(frame.set_index("timestamp").dropna())
    if not frames:
        raise DataUnavailable(
            "Weather history is unavailable. A weather-based forecast cannot be produced."
        )
    return (
        pd.concat(frames).loc[lambda x: ~x.index.duplicated(keep="last")].sort_index()
    )


def collect(location):
    key = get_settings().openaq_api_key.strip()
    if not key or key.startswith("YOUR_"):
        raise DataUnavailable(
            "Add OPENAQ_API_KEY to the server .env file, then restart the API to connect live observations."
        )
    with _lock:
        cached = _cache.get(location.id)
        if cached and time.monotonic() - cached[0] < 600:
            return cached[1]
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=45)
        stations = []
        with httpx.Client(
            timeout=provider_timeout(), headers={"X-API-Key": key}
        ) as client:
            locations = sorted(
                discover_locations(client, location),
                key=lambda loc: ((loc.get("datetimeLast") or {}).get("utc") or ""),
                reverse=True,
            )
            # Keep recency first: stale paired monitors must not hide fresh
            # single-pollutant stations. Bound requests to protect API quota.
            for loc in locations[:16]:
                sensors = {
                    s["id"]: parameter(s)
                    for s in loc.get("sensors", [])
                    if parameter(s)
                }
                if not sensors:
                    continue
                last_seen = (loc.get("datetimeLast") or {}).get("utc")
                if last_seen and (pd.Timestamp(now)-pd.Timestamp(last_seen)).total_seconds() > 86400:
                    latest = {"results": []}
                else:
                    try:
                        latest = request(client, f"{BASE}/locations/{loc['id']}/latest", params={"limit": 100})
                    except DataUnavailable as exc:
                        raise DataUnavailable(str(exc), stations=stations) from None
                readings = {}
                for item in latest.get("results") or []:
                    name = sensors.get(item.get("sensorsId"))
                    stamp = (item.get("datetime") or {}).get("utc")
                    if name and stamp and valid_value(item.get("value")):
                        ts = pd.Timestamp(stamp)
                        age = (pd.Timestamp(now) - ts).total_seconds() / 3600
                        if -0.25 <= age <= 24 and (
                            name not in readings
                            or ts > pd.Timestamp(readings[name]["observed_at"])
                        ):
                            readings[name] = {
                                "value": item["value"],
                                "observed_at": stamp,
                                "sensor_id": item["sensorsId"],
                                "age_hours": round(age, 1),
                            }
                coords = loc.get("coordinates") or {}
                stations.append(
                    {
                        "id": loc["id"],
                        "name": loc["name"],
                        "distance_km": loc["distance_km"],
                        "latitude": coords.get("latitude"),
                        "longitude": coords.get("longitude"),
                        "provider": (loc.get("provider") or {}).get(
                            "name", "OpenAQ contributor"
                        ),
                        "readings": readings,
                        "selected": False,
                    }
                )
            candidates = [
                s for s in stations if all(p in s["readings"] for p in ("pm25", "pm10"))
            ]
            if not candidates:
                raise DataUnavailable(
                    "OpenAQ is connected, but no checked station within 125 km has both pollutants updated in the last 24 hours. The paired station forecast is unavailable; independent sources are required.",
                    stations=stations,
                )
            selected = min(
                candidates,
                key=lambda s: (s["distance_km"], max(r["age_hours"] for r in s["readings"].values())),
            )
            selected["selected"] = True
            try:
                columns = {
                    p: sensor_hours(client, selected["readings"][p]["sensor_id"], start, now)
                    for p in ("pm25", "pm10")
                }
            except DataUnavailable as exc:
                raise DataUnavailable(str(exc), stations=stations) from None
        # Do not send the OpenAQ credential to the weather provider.
        with httpx.Client(timeout=provider_timeout()) as weather_client:
            try:
                meteo = weather(weather_client, location, start, now)
            except DataUnavailable as exc:
                raise DataUnavailable(str(exc), stations=stations) from None
        frame = pd.DataFrame(columns).sort_index()
        frame = frame.reindex(
            pd.date_range(
                start=pd.Timestamp(start).ceil("h"),
                end=pd.Timestamp(now).floor("h"),
                freq="h",
            )
        )
        frame = frame.join(meteo).rename_axis("timestamp").reset_index()
        complete = frame.dropna()
        if len(complete) < 2:
            raise DataUnavailable(
                "Not enough aligned PM2.5, PM10 and weather observations at this station.", stations=stations
            )
        last = complete.timestamp.max()
        if (pd.Timestamp(now) - last).total_seconds() > 24 * 3600:
            raise DataUnavailable(
                "The most recent complete hourly observation is older than 24 hours. No current forecast is available.", stations=stations
            )
        frame = frame[frame.timestamp <= last].reset_index(drop=True)
        result = {
            "frame": frame,
            "stations": stations,
            "station": selected,
            "source": "OpenAQ + Open-Meteo",
            "mode": "live",
            "coverage_pct": round(100 * len(complete) / len(frame), 1),
            "collected_at": now.isoformat(),
            "warnings": [
                f"Selected station is {selected['distance_km']} km from the city centre. Readings represent that monitor, not a city-wide average.",
                "Weather is Open-Meteo reanalysis/model data. Missing hours are excluded; synthetic observations are never inserted.",
            ],
        }
        out = get_settings().processed_dir / f"{location.id}-openaq.csv"
        frame.to_csv(out, index=False)
        _cache[location.id] = (time.monotonic(), result)
        return result
