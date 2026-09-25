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


INDIAN_CENTRES = [
    ("bangalore", "Bengaluru (Bangalore)", 12.9716, 77.5946),
    ("hyderabad", "Hyderabad", 17.3850, 78.4867),
    ("chennai", "Chennai", 13.0827, 80.2707),
    ("kolkata", "Kolkata", 22.5726, 88.3639),
    ("pune", "Pune", 18.5204, 73.8567),
    ("ahmedabad", "Ahmedabad", 23.0225, 72.5714),
    ("surat", "Surat", 21.1702, 72.8311),
    ("jaipur", "Jaipur", 26.9124, 75.7873),
    ("lucknow", "Lucknow", 26.8467, 80.9462),
    ("kanpur", "Kanpur", 26.4499, 80.3319),
    ("nagpur", "Nagpur", 21.1458, 79.0882),
    ("indore", "Indore", 22.7196, 75.8577),
    ("bhopal", "Bhopal", 23.2599, 77.4126),
    ("patna", "Patna", 25.5941, 85.1376),
    ("chandigarh", "Chandigarh", 30.7333, 76.7794),
    ("kochi", "Kochi", 9.9312, 76.2673),
    ("thiruvananthapuram", "Thiruvananthapuram", 8.5241, 76.9366),
    ("coimbatore", "Coimbatore", 11.0168, 76.9558),
    ("visakhapatnam", "Visakhapatnam", 17.6868, 83.2185),
    ("vijayawada", "Vijayawada", 16.5062, 80.6480),
    ("bhubaneswar", "Bhubaneswar", 20.2961, 85.8245),
    ("guwahati", "Guwahati", 26.1445, 91.7362),
    ("ranchi", "Ranchi", 23.3441, 85.3096),
    ("raipur", "Raipur", 21.2514, 81.6296),
    ("noida", "Noida", 28.5355, 77.3910),
    ("gurugram", "Gurugram", 28.4595, 77.0266),
    ("ghaziabad", "Ghaziabad", 28.6692, 77.4538),
    ("faridabad", "Faridabad", 28.4089, 77.3178),
    ("agra", "Agra", 27.1767, 78.0081),
    ("varanasi", "Varanasi", 25.3176, 82.9739),
    ("amritsar", "Amritsar", 31.6340, 74.8723),
    ("ludhiana", "Ludhiana", 30.9010, 75.8573),
    ("jodhpur", "Jodhpur", 26.2389, 73.0243),
    ("nashik", "Nashik", 19.9975, 73.7898),
    ("vadodara", "Vadodara", 22.3072, 73.1812),
    ("rajkot", "Rajkot", 22.3039, 70.8022),
    ("madurai", "Madurai", 9.9252, 78.1198),
    ("mysuru", "Mysuru", 12.2958, 76.6394),
    ("dehradun", "Dehradun", 30.3165, 78.0322),
    ("srinagar", "Srinagar", 34.0837, 74.7973),
]
for cid, name, lat, lon in INDIAN_CENTRES:
    CITIES[cid] = Location(id=cid, city=name, country="IN", latitude=lat,
                          longitude=lon, timezone="Asia/Kolkata", industrial_zones=[])


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
