from fastapi.testclient import TestClient

from app.aqi import aqi_from_pm
from app.main import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_live_partial_observations_survive_unavailable_forecast(monkeypatch):
    from app.data.openaq import DataUnavailable

    stations = [{"id": 1, "readings": {"pm25": {"value": 38.6}}}]

    def unavailable(*args):
        raise DataUnavailable("Paired forecast unavailable", stations=stations)

    monkeypatch.setattr("app.api.city_snapshot", unavailable)
    response = TestClient(app).get("/api/v1/forecast/delhi?mode=live")
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "message": "Paired forecast unavailable",
        "stations": stations,
        "connected": True,
    }


def test_locations() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/locations")
    assert resp.status_code == 200
    cities = {row["id"] for row in resp.json()}
    assert "delhi" in cities
    assert "los-angeles" in cities


def test_aqi_breakpoints() -> None:
    aqi, category, dominant = aqi_from_pm(9, 20)
    assert category == "Good"
    assert dominant in {"pm25", "pm10"}
    aqi, category, _ = aqi_from_pm(80, 40)
    assert aqi >= 151
    assert "Unhealthy" in category
