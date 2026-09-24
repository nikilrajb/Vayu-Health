"""OpenAQ v3 ingestion with bounded pagination, provenance and explicit failures."""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx
import pandas as pd

from app.config import get_settings

BASE = "https://api.openaq.org/v3"
_cache: dict = {}
_lock = Lock()


class DataUnavailable(RuntimeError):
    pass


def request(client, url, **kwargs):
    host = httpx.URL(url).host
    provider = "OpenAQ" if host == "api.openaq.org" else "Weather provider"
    retries = getattr(get_settings(), "provider_retries", 1)
    for attempt in range(retries + 1):
        retry = False
        try:
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
        isinstance(value, (int, float))
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
    key = get_settings().openaq_api_key
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
            payload = request(
                client,
                f"{BASE}/locations",
                params={
                    "coordinates": f"{location.latitude},{location.longitude}",
                    "radius": 25000,
                    "limit": 1000,
                },
            )
            locations = sorted(
                payload.get("results") or [],
                key=lambda loc: ((loc.get("datetimeLast") or {}).get("utc") or ""),
                reverse=True,
            )
            # Prioritize paired PM stations before limiting requests; old IDs are
            # often retired stations and must not crowd out active monitors.
            locations.sort(
                key=lambda loc: not {"pm25", "pm10"}.issubset(
                    {parameter(s) for s in loc.get("sensors", [])}
                )
            )
            for loc in locations[:8]:
                sensors = {
                    s["id"]: parameter(s)
                    for s in loc.get("sensors", [])
                    if parameter(s)
                }
                if not sensors:
                    continue
                latest = request(
                    client,
                    f"{BASE}/locations/{loc['id']}/latest",
                    params={"limit": 100},
                )
                readings = {}
                for item in latest.get("results") or []:
                    name = sensors.get(item.get("sensorsId"))
                    stamp = (item.get("datetime") or {}).get("utc")
                    if name and stamp and valid_value(item.get("value")):
                        ts = pd.Timestamp(stamp)
                        age = (pd.Timestamp(now) - ts).total_seconds() / 3600
                        if -0.25 <= age <= 24:
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
                    "No station within 25 km has both PM2.5 and PM10 measurements from the last 24 hours. Coverage varies by city; try another location or the explicit demo."
                )
            selected = min(
                candidates,
                key=lambda s: max(r["age_hours"] for r in s["readings"].values()),
            )
            selected["selected"] = True
            columns = {
                p: sensor_hours(
                    client, selected["readings"][p]["sensor_id"], start, now
                )
                for p in ("pm25", "pm10")
            }
        # Do not send the OpenAQ credential to the weather provider.
        with httpx.Client(timeout=provider_timeout()) as weather_client:
            meteo = weather(weather_client, location, start, now)
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
                "Not enough aligned PM2.5, PM10 and weather observations at this station."
            )
        last = complete.timestamp.max()
        if (pd.Timestamp(now) - last).total_seconds() > 24 * 3600:
            raise DataUnavailable(
                "The most recent complete hourly observation is older than 24 hours. No current forecast is available."
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
                "Station readings represent their monitoring location, not a city-wide average.",
                "Weather is Open-Meteo reanalysis/model data. Missing hours are excluded; synthetic observations are never inserted.",
            ],
        }
        out = get_settings().processed_dir / f"{location.id}-openaq.csv"
        frame.to_csv(out, index=False)
        _cache[location.id] = (time.monotonic(), result)
        return result
