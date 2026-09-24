from __future__ import annotations

from app.schemas import Location

CITIES: dict[str, Location] = {
    "delhi": Location(
        id="delhi",
        city="Delhi",
        country="IN",
        latitude=28.6139,
        longitude=77.2090,
        timezone="Asia/Kolkata",
        industrial_zones=[
            "Bawana Industrial Area",
            "Okhla Industrial Estate",
            "Mayapuri Industrial Area",
            "Wazirpur Industrial Area",
        ],
    ),
    "mumbai": Location(
        id="mumbai",
        city="Mumbai",
        country="IN",
        latitude=19.0760,
        longitude=72.8777,
        timezone="Asia/Kolkata",
        industrial_zones=[
            "Taloja MIDC",
            "Trans-Thane Creek",
            "Mahape MIDC",
        ],
    ),
    "los-angeles": Location(
        id="los-angeles",
        city="Los Angeles",
        country="US",
        latitude=34.0522,
        longitude=-118.2437,
        timezone="America/Los_Angeles",
        industrial_zones=[
            "Port of Los Angeles",
            "Vernon Industrial Corridor",
            "Long Beach Refinery Belt",
        ],
    ),
    "london": Location(
        id="london",
        city="London",
        country="GB",
        latitude=51.5074,
        longitude=-0.1278,
        timezone="Europe/London",
        industrial_zones=[
            "Park Royal",
            "Thames Gateway",
            "Silvertown",
        ],
    ),
    "beijing": Location(
        id="beijing",
        city="Beijing",
        country="CN",
        latitude=39.9042,
        longitude=116.4074,
        timezone="Asia/Shanghai",
        industrial_zones=[
            "Shunyi Industrial Park",
            "Daxing Economic Zone",
            "Tongzhou Manufacturing Belt",
        ],
    ),
}


def get_location(city_id: str) -> Location:
    key = city_id.strip().lower().replace(" ", "-")
    if key not in CITIES:
        raise KeyError(f"Unknown city '{city_id}'. Choose from: {', '.join(CITIES)}")
    return CITIES[key]


# Typical baseline concentrations used when synthesizing demo series.
CITY_CLIMATE: dict[str, dict] = {
    "delhi": {
        "pm25_base": 95,
        "pm10_base": 170,
        "temp_mean": 28,
        "humidity": 48,
        "wind": 2.4,
        "pressure": 1008,
        "season_amp": 55,
    },
    "mumbai": {
        "pm25_base": 48,
        "pm10_base": 92,
        "temp_mean": 30,
        "humidity": 72,
        "wind": 3.1,
        "pressure": 1009,
        "season_amp": 22,
    },
    "los-angeles": {
        "pm25_base": 14,
        "pm10_base": 32,
        "temp_mean": 20,
        "humidity": 58,
        "wind": 3.6,
        "pressure": 1014,
        "season_amp": 8,
    },
    "london": {
        "pm25_base": 12,
        "pm10_base": 22,
        "temp_mean": 12,
        "humidity": 76,
        "wind": 4.2,
        "pressure": 1015,
        "season_amp": 6,
    },
    "beijing": {
        "pm25_base": 62,
        "pm10_base": 110,
        "temp_mean": 14,
        "humidity": 45,
        "wind": 2.8,
        "pressure": 1012,
        "season_amp": 40,
    },
}
