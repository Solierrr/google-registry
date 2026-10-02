"""Testes de app.infrastructure.google.routes.adapter.RoutesAdapter"""

import json
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.exceptions import (
    GoogleNotFoundException,
    GoogleRateLimitException,
    GoogleUnavailableException,
    GoogleUpstreamException,
    GoogleValidationException,
)
from app.infrastructure.google.routes.adapter import RoutesAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.routes import RouteRequest, Waypoint

BASE_URL = "https://routes.googleapis.com"
COMPUTE_ROUTES = f"{BASE_URL}/directions/v2:computeRoutes"

ORIGIN = Waypoint(latitude=-23.55, longitude=-46.63)
DESTINATION = Waypoint(latitude=-23.56, longitude=-46.65)
PAYLOAD = {
    "routes": [
        {"duration": "1260s", "distanceMeters": 8200, "polyline": {"encodedPolyline": "abc"}},
        {"duration": "1500s", "distanceMeters": 9100, "polyline": {"encodedPolyline": "def"}},
    ]
}


def _request(**overrides) -> RouteRequest:
    return RouteRequest(origin=ORIGIN, destination=DESTINATION, **overrides)


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="routes")
    yield RoutesAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_maps_routes_and_sends_key_and_field_mask_in_headers(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    result = await adapter.compute_routes(_request())

    assert [r.duration_seconds for r in result.routes] == [1260, 1500]
    assert result.routes[0].distance_meters == 8200
    assert result.routes[0].encoded_polyline == "abc"
    sent = route.calls.last.request
    assert sent.headers["X-Goog-Api-Key"] == "test-key"
    assert "routes.polyline.encodedPolyline" in sent.headers["X-Goog-FieldMask"]
    assert "test-key" not in str(sent.url)


@respx.mock
async def test_drive_request_is_traffic_aware_with_utc_departure_and_modifiers(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))
    departure = datetime(2030, 1, 2, 9, 30, tzinfo=timezone(timedelta(hours=-3)))

    await adapter.compute_routes(_request(departure_at=departure, avoid_tolls=True, avoid_highways=True))

    body = json.loads(route.calls.last.request.content)
    assert body["travelMode"] == "DRIVE"
    assert body["routingPreference"] == "TRAFFIC_AWARE"
    assert body["departureTime"] == "2030-01-02T12:30:00Z"
    assert body["routeModifiers"] == {"avoidTolls": True, "avoidHighways": True}
    assert body["computeAlternativeRoutes"] is True
    assert body["origin"] == {"location": {"latLng": {"latitude": -23.55, "longitude": -46.63}}}


@respx.mock
async def test_naive_departure_is_taken_as_utc(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    await adapter.compute_routes(_request(departure_at=datetime(2030, 1, 2, 9, 30)))

    assert json.loads(route.calls.last.request.content)["departureTime"] == "2030-01-02T09:30:00Z"


@respx.mock
async def test_drive_without_departure_or_modifiers_omits_them(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    await adapter.compute_routes(_request(alternatives=False))

    body = json.loads(route.calls.last.request.content)
    assert "departureTime" not in body
    assert "routeModifiers" not in body
    assert body["computeAlternativeRoutes"] is False


@respx.mock
async def test_walk_ignores_traffic_departure_and_modifiers(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=PAYLOAD))

    await adapter.compute_routes(
        _request(travel_mode="WALK", departure_at=datetime(2030, 1, 2, tzinfo=UTC), avoid_tolls=True)
    )

    body = json.loads(route.calls.last.request.content)
    assert body["travelMode"] == "WALK"
    assert "routingPreference" not in body
    assert "departureTime" not in body
    assert "routeModifiers" not in body


@respx.mock
async def test_returns_at_most_three_routes(adapter):
    routes = [{"duration": f"{n}s", "distanceMeters": n} for n in range(1, 6)]
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json={"routes": routes}))

    result = await adapter.compute_routes(_request())

    assert len(result.routes) == 3


@respx.mock
async def test_missing_polyline_is_allowed_and_malformed_routes_are_dropped(adapter):
    payload = {
        "routes": [
            {"duration": "600s", "distanceMeters": 1000},
            {"distanceMeters": 1},
            {"duration": "x", "distanceMeters": 1},
            "lixo",
        ]
    }
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=payload))

    result = await adapter.compute_routes(_request())

    assert len(result.routes) == 1
    assert result.routes[0].encoded_polyline is None


@respx.mock
@pytest.mark.parametrize("payload", [{}, {"routes": []}])
async def test_no_routes_is_not_found(adapter, payload):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(GoogleNotFoundException):
        await adapter.compute_routes(_request())


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, json=["lista"]),
        httpx.Response(200, json={"routes": "texto"}),
        httpx.Response(200, json={"routes": [{"distanceMeters": 1}]}),
    ],
)
async def test_unexpected_payload_is_upstream_error(adapter, response):
    respx.post(COMPUTE_ROUTES).mock(return_value=response)

    with pytest.raises(GoogleUpstreamException):
        await adapter.compute_routes(_request())


@respx.mock
async def test_bad_request_is_validation_error(adapter):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(400, json={"error": {"message": "past time"}}))

    with pytest.raises(GoogleValidationException):
        await adapter.compute_routes(_request())


@respx.mock
async def test_rate_limit_is_retried_then_raised(adapter):
    route = respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(429))

    with pytest.raises(GoogleRateLimitException):
        await adapter.compute_routes(_request())

    assert route.call_count == 3


@respx.mock
async def test_server_error_is_retried_then_succeeds(adapter):
    respx.post(COMPUTE_ROUTES).mock(side_effect=[httpx.Response(503), httpx.Response(200, json=PAYLOAD)])

    result = await adapter.compute_routes(_request())

    assert len(result.routes) == 2


@respx.mock
async def test_persistent_server_error_is_unavailable(adapter):
    respx.post(COMPUTE_ROUTES).mock(return_value=httpx.Response(503))

    with pytest.raises(GoogleUnavailableException):
        await adapter.compute_routes(_request())
