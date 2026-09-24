from fastapi.testclient import TestClient

from app.aqi import aqi_from_pm
from app.main import app


def test_health() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


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
