from __future__ import annotations

from datetime import datetime, timedelta

from app.aqi import aqi_from_pm
from app.schemas import AlertSeverity, HealthAlert, Location

POPULATIONS = [
    "Children under 12",
    "Adults 65+",
    "People with asthma or COPD",
    "Outdoor workers",
    "Pregnant people",
]


def _severity(aqi: int) -> AlertSeverity:
    if aqi >= 301:
        return "emergency"
    if aqi >= 151:
        return "warning"
    if aqi >= 101:
        return "watch"
    return "info"


def _title(category: str, aqi: int) -> str:
    return f"{category} air quality (AQI {aqi})"


def _message(city: str, category: str, aqi: int, hour_utc: str, pollutant: str) -> str:
    guidance = {
        "Good": "Usual outdoor activity is appropriate.",
        "Moderate": "Unusually sensitive people should consider shorter outdoor exertion.",
        "Unhealthy for Sensitive Groups": (
            "Sensitive groups should reduce prolonged or heavy outdoor exertion."
        ),
        "Unhealthy": "Reduce prolonged or heavy outdoor exertion, especially for sensitive groups. Follow local air-quality advisories.",
        "Very Unhealthy": "Consider rescheduling outdoor exertion and follow local public-health guidance.",
        "Hazardous": "Strongest forecast warning. Check local authority advisories and avoid outdoor exertion.",
    }
    return (
        f"{city}: forecast peak {category} (AQI {aqi}) driven by {pollutant.upper()} "
        f"around {hour_utc} UTC. {guidance.get(category, '')}"
    )


def build_alerts(
    location: Location,
    now: datetime,
    forecast_rows: list[dict],
) -> list[HealthAlert]:
    if not forecast_rows:
        return []

    peak = max(forecast_rows, key=lambda r: r["aqi"])
    aqi = int(peak["aqi"])
    category = peak["aqi_category"]
    pollutant = peak["dominant_pollutant"]
    peak_ts: datetime = peak["timestamp"]
    severity = _severity(aqi)

    alerts = [
        HealthAlert(
            id=f"{location.id}-peak-24h",
            severity=severity,
            title=_title(category, aqi),
            message=_message(
                location.city,
                category,
                aqi,
                peak_ts.strftime("%Y-%m-%d %H:%M"),
                pollutant,
            ),
            aqi=aqi,
            aqi_category=category,
            valid_from=now,
            valid_to=now + timedelta(hours=24),
            populations=POPULATIONS if aqi >= 101 else POPULATIONS[:3],
        )
    ]

    unhealthy_hours = [r for r in forecast_rows if r["aqi"] >= 151]
    if len(unhealthy_hours) >= 4:
        alerts.append(
            HealthAlert(
                id=f"{location.id}-sustained",
                severity="warning" if aqi < 301 else "emergency",
                title="Sustained unhealthy exposure window",
                message=(
                    f"{len(unhealthy_hours)} of the next 24 hours are forecast at Unhealthy or worse. "
                    "Review local advisories and prepare an operator-reviewed response before the first peak."
                ),
                aqi=aqi,
                aqi_category=category,
                valid_from=now,
                valid_to=now + timedelta(hours=24),
                populations=POPULATIONS,
            )
        )
    return alerts


def current_aqi_payload(pm25: float, pm10: float) -> tuple[int, str, str]:
    aqi, category, dominant = aqi_from_pm(pm25, pm10)
    return aqi, category, dominant
