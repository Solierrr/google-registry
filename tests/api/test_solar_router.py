"""Testes de GET /v1/solar/roof-viability"""

import httpx
import respx

FIND_CLOSEST = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
PAYLOAD = {
    "imageryDate": {"year": 2024, "month": 3, "day": 5},
    "solarPotential": {
        "maxArrayAreaMeters2": 42.5,
        "maxArrayPanelsCount": 20,
        "maxSunshineHoursPerYear": 1800.0,
        "carbonOffsetFactorKgPerMwh": 400.0,
        "roofSegmentStats": [{"pitchDegrees": 20.0, "azimuthDegrees": 180.0, "stats": {"areaMeters2": 42.5}}],
    },
}


@respx.mock
def test_roof_viability_returns_viability(client):
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json=PAYLOAD))

    response = client.get("/v1/solar/roof-viability", params={"latitude": -23.5, "longitude": -46.6})

    assert response.status_code == 200
    assert response.json()["max_panel_count"] == 20


def test_roof_viability_rejects_out_of_range_latitude(client):
    response = client.get("/v1/solar/roof-viability", params={"latitude": 100, "longitude": 0})

    assert response.status_code == 422


@respx.mock
def test_roof_viability_returns_404_without_coverage(client):
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(404))

    response = client.get("/v1/solar/roof-viability", params={"latitude": -23.5, "longitude": -46.6})

    assert response.status_code == 404
    assert response.json()["code"] == "GoogleNotFoundException"
