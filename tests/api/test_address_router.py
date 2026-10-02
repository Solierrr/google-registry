"""Testes de /v1/address/suggestions e /v1/address/places/{place_id}"""

import httpx
import respx

PLACES = "https://places.googleapis.com"


@respx.mock
def test_suggestions_returns_suggestions(client):
    respx.post(f"{PLACES}/v1/places:autocomplete").mock(
        return_value=httpx.Response(
            200, json={"suggestions": [{"placePrediction": {"placeId": "ChIJ1", "text": {"text": "Av. Paulista"}}}]}
        )
    )

    response = client.post("/v1/address/suggestions", json={"query": "paulista"})

    assert response.status_code == 200
    assert response.json() == {
        "suggestions": [{"place_id": "ChIJ1", "description": "Av. Paulista", "main_text": None, "secondary_text": None}]
    }


def test_suggestions_rejects_short_query(client):
    response = client.post("/v1/address/suggestions", json={"query": "av"})

    assert response.status_code == 422


@respx.mock
def test_place_details_returns_address(client):
    respx.get(f"{PLACES}/v1/places/ChIJ1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "ChIJ1",
                "formattedAddress": "Av. Paulista, 1000",
                "location": {"latitude": -23.5, "longitude": -46.6},
            },
        )
    )

    response = client.get("/v1/address/places/ChIJ1", params={"session_token": "tok"})

    assert response.status_code == 200
    assert response.json()["formatted_address"] == "Av. Paulista, 1000"
    assert response.json()["latitude"] == -23.5


@respx.mock
def test_place_details_returns_404_for_unknown_place(client):
    respx.get(f"{PLACES}/v1/places/missing").mock(return_value=httpx.Response(404))

    response = client.get("/v1/address/places/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "GoogleNotFoundException"
