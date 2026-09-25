from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.aqi import aqi_from_pm
from app.schemas import HealthAlert, Location

POPULATIONS = ["People with heart or lung conditions", "Older adults", "Children and teenagers", "Outdoor workers"]
GUIDANCE = {
    "Good": "Usual outdoor activity is appropriate; keep checking for forecast changes.",
    "Moderate": "Unusually sensitive people can consider shorter outdoor exertion.",
    "Unhealthy for Sensitive Groups": "Sensitive groups should reduce prolonged or heavy outdoor exertion.",
    "Unhealthy": "Reduce prolonged or heavy outdoor exertion, especially for sensitive groups.",
    "Very Unhealthy": "Reschedule outdoor exertion and follow local public-health advice.",
    "Hazardous": "Avoid outdoor exertion and check urgent local authority advisories.",
}


def _severity(risk):
    return "emergency" if risk >= 301 else "warning" if risk >= 151 else "watch" if risk >= 101 else "info"


def build_alerts(location: Location, now: datetime, forecast_rows: list[dict]) -> list[HealthAlert]:
    rows = sorted((r for r in forecast_rows if r["timestamp"] > now), key=lambda r:r["timestamp"])
    if not rows:
        return []
    timezone = ZoneInfo(location.timezone)
    def local(stamp):
        return stamp.astimezone(timezone).strftime("%d %b %H:%M %Z")
    # Distinct contiguous elevated periods, not a misleading count of scattered hours.
    windows = []
    for row in rows:
        if row["aqi"] < 101:
            continue
        if windows and row["timestamp"] - windows[-1][-1]["timestamp"] == timedelta(hours=1):
            windows[-1].append(row)
        else:
            windows.append([row])
    if not windows:
        windows = [rows]
    alerts = []
    for index, window in enumerate(windows):
        peak = max(window, key=lambda r:r["aqi"])
        risk, category = int(peak["aqi"]), peak["aqi_category"]
        high = sum(r["aqi"] >= 151 for r in window)
        text = (f"{location.city}: {len(window)} forecast hours from {local(window[0]['timestamp'])} to {local(window[-1]['timestamp'])}. "
                f"Peak screening index {risk} at {local(peak['timestamp'])}, driven by {peak['dominant_pollutant'].upper()}. "
                f"PM2.5 {peak['pm25']:.1f} and PM10 {peak['pm10']:.1f} µg/m³ at the peak. "
                f"{high} hours reach index 151 or above. {GUIDANCE.get(category, '')} "
                "This is forecast screening, not an official AQI advisory or a diagnosis.")
        alerts.append(HealthAlert(id=f"{location.id}-window-{index}-{window[0]['timestamp'].isoformat()}",
            severity=_severity(risk), title=f"{category}: {'elevated period' if risk >= 101 else 'outlook'}",
            message=text, aqi=risk, aqi_category=category,
            valid_from=window[0]["timestamp"], valid_to=window[-1]["timestamp"]+timedelta(hours=1), populations=POPULATIONS))
    # A relative lower-exposure window is useful, but never label it 'safe'.
    candidates = [rows[i:i+3] for i in range(len(rows)-2) if rows[i+2]["timestamp"]-rows[i]["timestamp"] == timedelta(hours=2)]
    if candidates and max(r["aqi"] for r in rows) >= 101:
        low = min(candidates, key=lambda group:sum(r["aqi"] for r in group))
        highest = max(low,key=lambda r:r["aqi"])
        alerts.append(HealthAlert(id=f"{location.id}-lower-window", severity="info", title="Lowest predicted three-hour window",
            message=f"{local(low[0]['timestamp'])} to {local(low[-1]['timestamp'])} has the lowest average predicted screening index ({sum(r['aqi'] for r in low)/3:.0f}). Peak within this window: {highest['aqi']}. Use this relative comparison to consider rescheduling outdoor work; it is not a guarantee of safe air. Confirm fresh local measurements first.",
            aqi=highest["aqi"], aqi_category=highest["aqi_category"], valid_from=low[0]["timestamp"], valid_to=low[-1]["timestamp"]+timedelta(hours=1), populations=POPULATIONS))
    return alerts


def current_aqi_payload(pm25: float, pm10: float) -> tuple[int, str, str]:
    return aqi_from_pm(pm25, pm10)
