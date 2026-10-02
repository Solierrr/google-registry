"""Testes de POST /v1/routes/compute"""

import httpx
import respx

COMPUTE_ROUTES = "https://routes.googleapis.com/directions/v2:computeRoutes"
BODY = {
    "origin": {"latitude": -23.55, "longitude": -46.63},
    "destination": {"latitude": -23.56, "longitude": -46.65},
}
PAYLOAD = {"routes": [{"duration": "1260s", "distanceMeters": 8200, "polyline": {"encodedPolyline": "abc"}}]}


@respx.mock
def test_compute_returns_routes(client):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    response = client.post("/v1/routes/compute", json=BODY)

    assert response.status_code == 200
    assert response.json() == {
        "routes": [{"duration_seconds": 1260, "distance_meters": 8200, "encoded_polyline": "abc"}]
    }


@respx.mock
def test_compute_passes_the_travel_options(client):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    client.post(
        "/v1/routes/compute",
        json={**BODY, "travel_mode": "WALK", "alternatives": False},
    )

    sent = route.calls.last.request.content
    assert b'"travelMode":"WALK"' in sent
    assert b'"computeAlternativeRoutes":false' in sent


def test_compute_rejects_out_of_range_coordinates(client):
    response = client.post(
        "/v1/routes/compute",
        json={**BODY, "origin": {"latitude": 100, "longitude": 0}},
    )

    assert response.status_code == 422


def test_compute_rejects_unsupported_travel_mode(client):
    response = client.post("/v1/routes/compute", json={**BODY, "travel_mode": "BICYCLE"})

    assert response.status_code == 422


@respx.mock
def test_compute_returns_404_without_routes(client):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json={}))

    response = client.post("/v1/routes/compute", json=BODY)

    assert response.status_code == 404
    assert response.json()["code"] == "GoogleNotFoundException"


@respx.mock
def test_compute_maps_google_bad_request_to_400(client):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(400, json={"error": {"message": "past"}}))

    response = client.post("/v1/routes/compute", json=BODY)

    assert response.status_code == 400
