import json

import httpx
import pytest
import respx

from app.exceptions import GoogleNotFoundException, GoogleUpstreamException, GoogleValidationException
from app.infrastructure.google.places.adapter import PlacesAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://places.googleapis.com"

SUGGESTIONS_PAYLOAD = {
    "suggestions": [
        {
            "placePrediction": {
                "placeId": "ChIJ1",
                "text": {"text": "Avenida Paulista, 1000 - Bela Vista, São Paulo - SP, Brasil"},
                "structuredFormat": {
                    "mainText": {"text": "Avenida Paulista, 1000"},
                    "secondaryText": {"text": "Bela Vista, São Paulo - SP"},
                },
            }
        },
        {"queryPrediction": {"text": {"text": "avenida paulista"}}},
        {"placePrediction": {"placeId": "ChIJ2"}},
    ]
}

DETAILS_PAYLOAD = {
    "id": "ChIJ1",
    "formattedAddress": "Av. Paulista, 1000 - Bela Vista, São Paulo - SP, 01310-100, Brasil",
    "location": {"latitude": -23.5614, "longitude": -46.6559},
    "addressComponents": [
        {"longText": "1000", "shortText": "1000", "types": ["street_number"]},
        {"longText": "Avenida Paulista", "shortText": "Av. Paulista", "types": ["route"]},
        {"longText": "Bela Vista", "shortText": "Bela Vista", "types": ["sublocality_level_1", "sublocality"]},
        {"longText": "São Paulo", "shortText": "São Paulo", "types": ["administrative_area_level_2", "political"]},
        {"longText": "São Paulo", "shortText": "SP", "types": ["administrative_area_level_1", "political"]},
        {"longText": "Brasil", "shortText": "BR", "types": ["country", "political"]},
        {"longText": "01310-100", "shortText": "01310-100", "types": ["postal_code"]},
        {"longText": "Sala 5", "shortText": "Sala 5", "types": ["subpremise"]},
    ],
}


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="places")
    yield PlacesAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_suggest_maps_place_predictions_and_skips_the_rest(adapter):
    route = respx.post(f"{BASE_URL}/v1/places:autocomplete").mock(
        return_value=httpx.Response(200, json=SUGGESTIONS_PAYLOAD)
    )

    result = await adapter.suggest("av paulista", session_token="tok", language="pt-BR", country="BR")

    assert [s.place_id for s in result] == ["ChIJ1"]
    assert result[0].main_text == "Avenida Paulista, 1000"
    assert result[0].secondary_text == "Bela Vista, São Paulo - SP"
    request = route.calls.last.request
    assert request.headers["X-Goog-Api-Key"] == "test-key"
    body = json.loads(request.read())
    assert body == {
        "input": "av paulista",
        "languageCode": "pt-BR",
        "includedRegionCodes": ["br"],
        "sessionToken": "tok",
    }


@respx.mock
async def test_suggest_returns_empty_list_when_google_has_no_suggestions(adapter):
    respx.post(f"{BASE_URL}/v1/places:autocomplete").mock(return_value=httpx.Response(200, json={}))

    assert await adapter.suggest("zzzzz", session_token=None, language="pt-BR", country="BR") == []


@respx.mock
async def test_suggest_rejects_malformed_payload(adapter):
    respx.post(f"{BASE_URL}/v1/places:autocomplete").mock(
        return_value=httpx.Response(200, json={"suggestions": "invalid"})
    )

    with pytest.raises(GoogleUpstreamException):
        await adapter.suggest("av paulista", session_token=None, language="pt-BR", country="BR")


@respx.mock
async def test_get_details_maps_components_and_requests_a_minimal_field_mask(adapter):
    route = respx.get(f"{BASE_URL}/v1/places/ChIJ1").mock(return_value=httpx.Response(200, json=DETAILS_PAYLOAD))

    result = await adapter.get_details("ChIJ1", session_token="tok", language="pt-BR")

    assert result.place_id == "ChIJ1"
    assert result.street_name == "Avenida Paulista"
    assert result.street_number == "1000"
    assert result.complement == "Sala 5"
    assert result.neighborhood == "Bela Vista"
    assert result.city == "São Paulo"
    assert result.state == "SP"
    assert result.postal_code == "01310-100"
    assert result.country_code == "BR"
    assert (result.latitude, result.longitude) == (-23.5614, -46.6559)
    request = route.calls.last.request
    assert request.headers["X-Goog-FieldMask"] == "id,formattedAddress,addressComponents,location"
    assert request.url.params["sessionToken"] == "tok"
    assert request.url.params["languageCode"] == "pt-BR"


@respx.mock
async def test_get_details_leaves_missing_components_empty(adapter):
    payload = {**DETAILS_PAYLOAD, "addressComponents": []}
    respx.get(f"{BASE_URL}/v1/places/ChIJ1").mock(return_value=httpx.Response(200, json=payload))

    result = await adapter.get_details("ChIJ1", session_token=None, language="pt-BR")

    assert result.street_name is None
    assert result.city is None
    assert result.formatted_address.startswith("Av. Paulista")


@respx.mock
async def test_get_details_uses_locality_when_present(adapter):
    components = [{"longText": "Campinas", "shortText": "Campinas", "types": ["locality"]}]
    respx.get(f"{BASE_URL}/v1/places/ChIJ1").mock(
        return_value=httpx.Response(200, json={**DETAILS_PAYLOAD, "addressComponents": components})
    )

    assert (await adapter.get_details("ChIJ1", session_token=None, language="pt-BR")).city == "Campinas"


@respx.mock
async def test_get_details_translates_not_found(adapter):
    respx.get(f"{BASE_URL}/v1/places/missing").mock(return_value=httpx.Response(404))

    with pytest.raises(GoogleNotFoundException, match="place_id"):
        await adapter.get_details("missing", session_token=None, language="pt-BR")


@respx.mock
async def test_get_details_quotes_the_place_id_in_the_path(adapter):
    route = respx.get(url__regex=rf"{BASE_URL}/v1/places/.*").mock(
        return_value=httpx.Response(200, json=DETAILS_PAYLOAD)
    )

    await adapter.get_details("a/b?c", session_token=None, language="pt-BR")

    assert route.calls.last.request.url.raw_path.split(b"?")[0] == b"/v1/places/a%2Fb%3Fc"


@respx.mock
async def test_get_details_rejects_payload_without_location(adapter):
    payload = {k: v for k, v in DETAILS_PAYLOAD.items() if k != "location"}
    respx.get(f"{BASE_URL}/v1/places/ChIJ1").mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(GoogleUpstreamException):
        await adapter.get_details("ChIJ1", session_token=None, language="pt-BR")


@respx.mock
async def test_bad_request_becomes_validation_error(adapter):
    respx.post(f"{BASE_URL}/v1/places:autocomplete").mock(return_value=httpx.Response(400, json={"error": "bad"}))

    with pytest.raises(GoogleValidationException):
        await adapter.suggest("abc", session_token=None, language="xx", country="BR")
