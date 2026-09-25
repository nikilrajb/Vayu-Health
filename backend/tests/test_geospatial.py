import httpx
from app.catalog import CITIES
from app.data.openaq import discover_locations, distance_km


def test_125km_search_uses_bbox_and_excludes_rectangle_corners():
    city = CITIES["mumbai"]
    rows = [
        {"id": 1, "coordinates": {"latitude": city.latitude, "longitude": city.longitude}},
        {"id": 2, "coordinates": {"latitude": city.latitude+1, "longitude": city.longitude}},
        {"id": 3, "coordinates": {"latitude": city.latitude+1, "longitude": city.longitude+1}},
        {"id": 4, "coordinates": None},
    ]
    def handler(req):
        assert "bbox" in req.url.params
        assert "radius" not in req.url.params
        assert "coordinates" not in req.url.params
        west, south, east, north = map(float, req.url.params["bbox"].split(","))
        assert west < city.longitude < east
        assert south < city.latitude < north
        return httpx.Response(200, json={"results": rows})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = discover_locations(client, city)
    assert [x["id"] for x in result] == [1, 2]
    assert result[0]["distance_km"] == 0
    assert 111 < result[1]["distance_km"] < 112


def test_distance_symmetry_and_boundary():
    assert distance_km(20, 70, 20, 70) == 0
    assert abs(distance_km(20, 70, 21, 71)-distance_km(21, 71, 20, 70)) < 1e-8
