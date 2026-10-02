"""Testes de app.infrastructure.google.address_validation.adapter.AddressValidationAdapter"""

import json

import httpx
import pytest
import respx

from app.exceptions import GoogleUpstreamException, GoogleValidationException
from app.infrastructure.google.address_validation.adapter import AddressValidationAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import ValidateRequest

BASE_URL = "https://addressvalidation.googleapis.com"
URL = f"{BASE_URL}/v1:validateAddress"

GOOD_RESULT = {
    "verdict": {
        "validationGranularity": "PREMISE",
        "addressComplete": True,
        "hasUnconfirmedComponents": False,
    },
    "address": {
        "formattedAddress": "Av. Paulista, 1000 - Bela Vista, São Paulo - SP, 01310-100, Brasil",
        "postalAddress": {
            "regionCode": "BR",
            "postalCode": "01310-100",
            "administrativeArea": "SP",
            "locality": "São Paulo",
        },
        "addressComponents": [
            {"componentName": {"text": "1000"}, "componentType": "street_number"},
            {"componentName": {"text": "Avenida Paulista"}, "componentType": "route"},
            {"componentName": {"text": "Bela Vista"}, "componentType": "sublocality_level_1"},
        ],
    },
    "geocode": {"location": {"latitude": -23.5614, "longitude": -46.6559}, "placeId": "ChIJ1"},
}


def _request(**overrides) -> ValidateRequest:
    return ValidateRequest(**{"address_lines": ["Av Paulista 1000"], **overrides})


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="address_validation")
    yield AddressValidationAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_complete_confirmed_address_is_ok_and_normalized(adapter):
    route = respx.post(URL).mock(return_value=httpx.Response(200, json={"result": GOOD_RESULT}))

    result = await adapter.validate(_request(postal_code="01310100", locality="São Paulo", administrative_area="SP"))

    assert result.verdict == "ok"
    assert result.missing_components == []
    assert result.unconfirmed_components == []
    assert result.address is not None
    assert result.address.street_name == "Avenida Paulista"
    assert result.address.street_number == "1000"
    assert result.address.neighborhood == "Bela Vista"
    assert (result.address.city, result.address.state, result.address.postal_code) == ("São Paulo", "SP", "01310-100")
    assert result.address.country_code == "BR"
    assert result.address.place_id == "ChIJ1"
    request = route.calls.last.request
    assert request.headers["X-Goog-Api-Key"] == "test-key"
    assert json.loads(request.read()) == {
        "address": {
            "regionCode": "BR",
            "addressLines": ["Av Paulista 1000"],
            "postalCode": "01310100",
            "locality": "São Paulo",
            "administrativeArea": "SP",
        }
    }


@respx.mock
async def test_unconfirmed_components_need_review(adapter):
    result_payload = {
        **GOOD_RESULT,
        "verdict": {**GOOD_RESULT["verdict"], "hasUnconfirmedComponents": True},
        "address": {**GOOD_RESULT["address"], "unconfirmedComponentTypes": ["street_number"]},
    }
    respx.post(URL).mock(return_value=httpx.Response(200, json={"result": result_payload}))

    result = await adapter.validate(_request())

    assert result.verdict == "needs_review"
    assert result.unconfirmed_components == ["street_number"]


@respx.mock
async def test_missing_components_need_review_even_if_marked_complete(adapter):
    result_payload = {**GOOD_RESULT, "address": {**GOOD_RESULT["address"], "missingComponentTypes": ["postal_code"]}}
    respx.post(URL).mock(return_value=httpx.Response(200, json={"result": result_payload}))

    result = await adapter.validate(_request())

    assert result.verdict == "needs_review"
    assert result.missing_components == ["postal_code"]


@respx.mock
async def test_address_without_validation_granularity_is_invalid_and_has_no_address(adapter):
    result_payload = {"verdict": {"validationGranularity": "OTHER", "addressComplete": False}, "address": {}}
    respx.post(URL).mock(return_value=httpx.Response(200, json={"result": result_payload}))

    result = await adapter.validate(_request())

    assert result.verdict == "invalid"
    assert result.address is None


@respx.mock
async def test_address_without_geocode_is_returned_without_coordinates(adapter):
    result_payload = {**GOOD_RESULT, "geocode": {}}
    respx.post(URL).mock(return_value=httpx.Response(200, json={"result": result_payload}))

    result = await adapter.validate(_request())

    assert result.verdict == "ok"
    assert result.address is None


@respx.mock
async def test_bad_request_becomes_validation_error(adapter):
    respx.post(URL).mock(return_value=httpx.Response(400, json={"error": {"message": "bad"}}))

    with pytest.raises(GoogleValidationException):
        await adapter.validate(_request(region_code="XX"))


@respx.mock
async def test_payload_without_result_is_upstream_error(adapter):
    respx.post(URL).mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.validate(_request())


@respx.mock
async def test_non_json_body_is_upstream_error(adapter):
    respx.post(URL).mock(return_value=httpx.Response(200, text="oops"))

    with pytest.raises(GoogleUpstreamException):
        await adapter.validate(_request())
