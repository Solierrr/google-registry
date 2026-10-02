import httpx
import pytest
import respx

from app.exceptions import (
    GoogleAuthenticationException,
    GoogleRateLimitException,
    GoogleUnavailableException,
    GoogleUpstreamException,
    GoogleValidationException,
)
from app.infrastructure.google.geocoding.adapter import GeocodingAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://maps.googleapis.com"
URL = f"{BASE_URL}/maps/api/geocode/json"

RESULT = {
    "place_id": "ChIJ1",
    "formatted_address": "Av. Paulista, 1000 - Bela Vista, São Paulo - SP, 01310-100, Brasil",
    "partial_match": True,
    "geometry": {"location": {"lat": -23.5614, "lng": -46.6559}, "location_type": "ROOFTOP"},
    "address_components": [
        {"long_name": "1000", "short_name": "1000", "types": ["street_number"]},
        {"long_name": "Avenida Paulista", "short_name": "Av. Paulista", "types": ["route"]},
        {"long_name": "Bela Vista", "short_name": "Bela Vista", "types": ["sublocality_level_1", "sublocality"]},
        {"long_name": "São Paulo", "short_name": "São Paulo", "types": ["administrative_area_level_2"]},
        {"long_name": "São Paulo", "short_name": "SP", "types": ["administrative_area_level_1"]},
        {"long_name": "Brasil", "short_name": "BR", "types": ["country"]},
        {"long_name": "01310-100", "short_name": "01310-100", "types": ["postal_code"]},
    ],
}


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="geocoding")
    yield GeocodingAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_geocode_maps_result_and_restricts_to_brazil(adapter):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"status": "OK", "results": [RESULT]}))

    results = await adapter.geocode("Av. Paulista, 1000", language="pt-BR")

    assert len(results) == 1
    address = results[0]
    assert address.place_id == "ChIJ1"
    assert address.street_name == "Avenida Paulista"
    assert address.street_number == "1000"
    assert address.neighborhood == "Bela Vista"
    assert address.city == "São Paulo"
    assert address.state == "SP"
    assert address.postal_code == "01310-100"
    assert address.country_code == "BR"
    assert address.precision == "rooftop"
    assert address.partial_match is True
    assert (address.latitude, address.longitude) == (-23.5614, -46.6559)
    params = route.calls.last.request.url.params
    assert params["components"] == "country:BR"
    assert params["address"] == "Av. Paulista, 1000"
    assert params["key"] == "test-key"


@respx.mock
async def test_geocode_zero_results_is_an_empty_list(adapter):
    respx.get(URL).mock(return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []}))

    assert await adapter.geocode("zzz", language="pt-BR") == []


@respx.mock
async def test_reverse_geocode_sends_latlng(adapter):
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"status": "OK", "results": [RESULT]}))

    results = await adapter.reverse_geocode(-23.5614, -46.6559, language="pt-BR")

    assert len(results) == 1
    assert route.calls.last.request.url.params["latlng"] == "-23.5614,-46.6559"
    assert "components" not in route.calls.last.request.url.params


@respx.mock
async def test_unknown_location_type_leaves_precision_empty(adapter):
    result = {**RESULT, "geometry": {"location": {"lat": 1.0, "lng": 2.0}}}
    respx.get(URL).mock(return_value=httpx.Response(200, json={"status": "OK", "results": [result]}))

    assert (await adapter.geocode("x y z", language="pt-BR"))[0].precision is None


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        ("OVER_QUERY_LIMIT", GoogleRateLimitException),
        ("OVER_DAILY_LIMIT", GoogleRateLimitException),
        ("REQUEST_DENIED", GoogleAuthenticationException),
        ("INVALID_REQUEST", GoogleValidationException),
        ("UNKNOWN_ERROR", GoogleUnavailableException),
        ("SOMETHING_NEW", GoogleUpstreamException),
    ],
)
@respx.mock
async def test_error_status_in_body_becomes_domain_exception(adapter, status, exception):
    respx.get(URL).mock(return_value=httpx.Response(200, json={"status": status, "error_message": "detalhe"}))

    with pytest.raises(exception):
        await adapter.geocode("x y z", language="pt-BR")


@respx.mock
async def test_denied_request_does_not_expose_google_error_message(adapter):
    respx.get(URL).mock(
        return_value=httpx.Response(200, json={"status": "REQUEST_DENIED", "error_message": "API key restrictions"})
    )

    with pytest.raises(GoogleAuthenticationException) as exc_info:
        await adapter.geocode("x y z", language="pt-BR")

    assert "restrictions" not in str(exc_info.value)
    assert exc_info.value.details() is None


@respx.mock
async def test_malformed_result_is_upstream_error(adapter):
    respx.get(URL).mock(
        return_value=httpx.Response(200, json={"status": "OK", "results": [{"formatted_address": "x"}]})
    )

    with pytest.raises(GoogleUpstreamException):
        await adapter.geocode("x y z", language="pt-BR")


@respx.mock
async def test_non_json_body_is_upstream_error(adapter):
    respx.get(URL).mock(return_value=httpx.Response(200, text="not json"))

    with pytest.raises(GoogleUpstreamException):
        await adapter.geocode("x y z", language="pt-BR")
