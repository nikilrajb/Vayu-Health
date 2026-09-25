from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from app.catalog import CITIES
from app.data import resilient
from app.data.openaq import DataUnavailable
from app.ml.independent import forecast_pollutant


def test_independent_training_without_other_pollutant():
    end = pd.Timestamp.now(tz="UTC").floor("h")
    hours = np.arange(1080)
    series = pd.Series(30 + 12*np.sin(hours*2*np.pi/24), index=pd.date_range(end=end, periods=1080, freq="h"))
    result = forecast_pollutant(series, end)
    assert result["metrics"]["purge_hours"] == 30
    assert len(result["values"]) == 24
    assert np.isfinite(result["values"]).all()
    assert result["method"] == "Independent station Extra Trees"
    assert forecast_pollutant(series, end+pd.Timedelta(hours=7)) is None


@pytest.mark.parametrize("observed", [False, True])
def test_model_fallback_is_labelled_and_never_training_truth(monkeypatch, tmp_path, observed):
    monkeypatch.setattr(resilient, "collect_airnow", lambda location: ([], {}, "AirNow test disabled"))
    monkeypatch.setattr(resilient, "collect_weather", lambda *args: None)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    times = pd.date_range(now, periods=25, freq="h").astype(str).tolist()
    def fake_request(client, url, **kwargs):
        assert "X-API-Key" not in client.headers
        if "air-quality" in url:
            return {"hourly": {"time": times, "pm2_5": [12]*25, "pm10": [25]*25}}
        return {"hourly": {"time": times, "temperature_2m": [25]*25,
            "relative_humidity_2m": [60]*25, "wind_speed_10m": [2]*25,
            "wind_direction_10m": [180]*25, "surface_pressure": [1010]*25}}
    monkeypatch.setattr(resilient, "request", fake_request)
    monkeypatch.setattr(resilient, "get_settings", lambda: SimpleNamespace(processed_dir=tmp_path, openaq_api_key="secret"))
    history = pd.Series([40.]*50, index=pd.date_range(end=now-pd.Timedelta(hours=1), periods=50, freq="h"))
    monkeypatch.setattr(resilient, "sensor_hours", lambda *args: history)
    stations = [{"id": 1, "name": "Test", "provider": "Test", "readings": {
        "pm25": {"value": 40., "observed_at": (now-pd.Timedelta(hours=1)).isoformat(), "age_hours": 1, "sensor_id": 1}}, "selected": False}] if observed else []
    ds = resilient.resilient_dataset(CITIES["mumbai"], DataUnavailable("No paired station", stations))
    assert ds["provenance"]["pm10"]["current_kind"] == "regional model estimate"
    assert ds["prediction"]["interval10"] is None
    assert len(ds["prediction"]["pm10"]) == 24
    assert ds["quality"] == ("mixed_sources" if observed else "regional_model")
    if observed:
        assert ds["frame"].iloc[0].pm25 == 40
        assert ds["observed_history"].pm10.isna().all()
        assert ds["provenance"]["pm25"]["current_at"] != now.isoformat()
    else:
        assert ds["observed_history"].empty
    assert list((tmp_path / "forecast_runs").glob("*.json"))


def test_indian_city_catalog():
    assert sum(c.country == "IN" for c in CITIES.values()) == 42
    assert all(cid in CITIES for cid in ["bangalore", "chennai", "hyderabad", "kolkata", "pune", "guwahati"])
