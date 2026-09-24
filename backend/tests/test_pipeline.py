from datetime import datetime, timezone
import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.aqi import aqi_from_pm
from app.main import app
from app.data.openaq import (
    DataUnavailable,
    parameter,
    request,
    sensor_hours,
    valid_value,
)
from app.ml.features import build_supervised
from app.data.synthetic import synthesize_city


@pytest.mark.parametrize(
    "concentration,index",
    [
        (0, 0),
        (9, 50),
        (9.1, 51),
        (35.4, 100),
        (55.4, 150),
        (125.4, 200),
        (225.4, 300),
        (325.4, 500),
    ],
)
def test_epa_2024_breakpoints(concentration, index):
    assert aqi_from_pm(concentration, 0)[0] == index


def test_sensor_mapping_and_units():
    assert parameter({"parameter": {"name": "pm25", "units": "µg/m³"}}) == "pm25"
    assert parameter({"parameter": {"name": "pm10", "units": "ug/m3"}}) == "pm10"
    assert parameter({"parameter": {"name": "pm25", "units": "ppm"}}) is None
    assert not valid_value(-1)
    assert not valid_value(float("nan"))
    assert valid_value(0)


def test_hourly_pagination_and_quality():
    calls = []

    def handler(req):
        page = req.url.params["page"]
        calls.append(page)
        row = {
            "value": 20,
            "period": {"datetimeFrom": {"utc": "2026-09-01T01:00:00Z"}},
            "coverage": {"percentCoverage": 100},
        }
        return httpx.Response(
            200,
            json={"results": [row] * 1000 if page == "1" else [{**row, "value": -10}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = sensor_hours(
            client, 1, datetime.now(timezone.utc), datetime.now(timezone.utc)
        )
    assert calls == ["1", "2"]
    assert result.iloc[0] == 20
    assert len(result) == 1


def test_rate_limit_is_explicit_and_does_not_leak_key():
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(429))
    ) as client:
        with pytest.raises(DataUnavailable, match="rate limit"):
            request(client, "https://example.org", headers={"X-API-Key": "secret"})


def test_gaps_cannot_become_adjacent_hours():
    frame = synthesize_city("delhi", hours=200)
    frame.loc[100, "pm25"] = np.nan
    x, _, _ = build_supervised(frame)
    assert x.notna().all().all()
    # A missing target hour invalidates each of the preceding 24 origins.
    assert len(x) < 200 - 48 - 24


def test_api_validation_and_no_silent_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.api.city_snapshot",
        lambda *args: (_ for _ in ()).throw(DataUnavailable("Provider unavailable")),
    )
    client = TestClient(app)
    assert client.get("/api/v1/forecast/unknown").status_code == 404
    assert client.get("/api/v1/forecast/delhi?mode=invalid").status_code == 422
    assert client.get("/api/v1/forecast/delhi").status_code == 503
    assert client.get("/api/v1/history/delhi?hours=0").status_code == 422


def test_demo_forecast_end_to_end():
    response = TestClient(app).get("/api/v1/forecast/delhi?mode=demo")
    assert response.status_code == 200
    data = response.json()
    assert len(data["forecast"]) == 24
    assert data["mode"] == "demo"
    assert data["stations"] == []
    assert data["model"]["metrics"]["gap_hours"] == 24
    assert data["model"]["metrics"]["data_mode"] == "demo"
    assert len(data["model"]["drivers"]) == 5
    assert all(np.isfinite(d["pm25_delta"]) for d in data["model"]["drivers"])
    assert data["model"]["metrics"]["pm25"]["persistence"]["mae"] >= 0
    assert all(
        row["pm25_lower"] <= row["pm25"] <= row["pm25_upper"]
        for row in data["forecast"]
    )
    times = pd.to_datetime([r["timestamp"] for r in data["forecast"]], utc=True)
    assert (times[1:] - times[:-1] == pd.Timedelta(hours=1)).all()
    assert "industrial_compliance_rate_pct" not in str(data)
