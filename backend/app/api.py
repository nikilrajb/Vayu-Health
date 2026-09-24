from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from app.catalog import CITIES
from app.config import get_settings
from app.data.openaq import DataUnavailable
from app.services import city_snapshot, history, list_locations

router = APIRouter(prefix="/api/v1")


@router.get("/status")
def status():
    return {
        "openaq_configured": bool(get_settings().openaq_api_key),
        "live_provider": "OpenAQ v3",
        "weather_provider": "Open-Meteo",
        "cache_seconds": 600,
    }


@router.get("/locations")
def locations():
    return list_locations()


def check_city(city_id):
    if city_id not in CITIES:
        raise HTTPException(404, "Unknown city")


@router.get("/forecast/{city_id}")
def forecast(city_id: str, mode: Literal["live", "demo"] = "live"):
    check_city(city_id)
    try:
        return city_snapshot(city_id, mode)
    except DataUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


@router.get("/history/{city_id}")
def city_history(
    city_id: str,
    hours: int = Query(72, ge=24, le=720),
    mode: Literal["live", "demo"] = "live",
):
    check_city(city_id)
    try:
        frame = history(city_id, hours, mode).copy()
        frame["timestamp"] = frame.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "city_id": city_id,
            "mode": mode,
            "points": frame.replace({float("nan"): None}).to_dict(orient="records"),
        }
    except DataUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
