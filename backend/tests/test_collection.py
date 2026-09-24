"""Exercise the entire ingestion boundary without an external network or real key."""

from types import SimpleNamespace
import httpx
import pandas as pd
from app.catalog import CITIES
from app.data import openaq


def test_live_collection_sensor_join_weather_and_key_isolation(monkeypatch, tmp_path):
    now = pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(hours=1)
    times = pd.date_range(end=now, periods=100, freq="h")
    sensors = [
        {"id": 11, "parameter": {"name": "pm25", "units": "µg/m³"}},
        {"id": 12, "parameter": {"name": "pm10", "units": "µg/m³"}},
    ]
    calls = []

    def handler(req):
        calls.append(req)
        if req.url.host == "api.openaq.org":
            assert req.headers["X-API-Key"] == "test-key"
            if req.url.path == "/v3/locations":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": 1,
                                "name": "Test station",
                                "sensors": sensors,
                                "datetimeLast": {"utc": now.isoformat()},
                                "coordinates": {"latitude": 28.61, "longitude": 77.21},
                                "provider": {"name": "Test provider"},
                            }
                        ]
                    },
                )
            if req.url.path.endswith("/latest"):
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "sensorsId": sensor_id,
                                "value": value,
                                "datetime": {"utc": now.isoformat()},
                            }
                            for sensor_id, value in [(11, 23), (12, 45)]
                        ]
                    },
                )
            value = 23 if "/11/" in req.url.path else 45
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "value": value,
                            "period": {"datetimeFrom": {"utc": t.isoformat()}},
                            "coverage": {"percentCoverage": 100},
                        }
                        for t in times
                    ]
                },
            )
        assert "X-API-Key" not in req.headers
        return httpx.Response(
            200,
            json={
                "hourly": {
                    "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
                    "temperature_2m": [25] * 100,
                    "relative_humidity_2m": [60] * 100,
                    "wind_speed_10m": [3] * 100,
                    "wind_direction_10m": [180] * 100,
                    "surface_pressure": [1010] * 100,
                }
            },
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        openaq.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(
        openaq,
        "get_settings",
        lambda: SimpleNamespace(openaq_api_key="test-key", processed_dir=tmp_path),
    )
    monkeypatch.setattr(openaq, "_cache", {})
    result = openaq.collect(CITIES["delhi"])
    assert result["mode"] == "live"
    assert result["station"]["selected"]
    complete = result["frame"].dropna()
    assert len(complete) == 100
    assert complete.pm25.iloc[-1] == 23
    assert complete.pm10.iloc[-1] == 45
    assert complete.timestamp.iloc[-1] == now
    assert result["coverage_pct"] < 100  # missing hours remain visible
    assert (tmp_path / "delhi-openaq.csv").exists()
    count = len(calls)
    assert openaq.collect(CITIES["delhi"]) is result
    assert len(calls) == count
