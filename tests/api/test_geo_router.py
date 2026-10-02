"""Testes de GET /v1/geo/timezone"""


def test_timezone_returns_id_and_offset(client):
    response = client.get(
        "/v1/geo/timezone", params={"latitude": -3.1, "longitude": -60.0, "at": "2026-07-01T12:00:00Z"}
    )

    assert response.status_code == 200
    assert response.json() == {"timezone_id": "America/Manaus", "utc_offset_seconds": -14400}


def test_timezone_without_instant_uses_now(client):
    response = client.get("/v1/geo/timezone", params={"latitude": -23.55, "longitude": -46.63})

    assert response.status_code == 200
    assert response.json()["timezone_id"] == "America/Sao_Paulo"


def test_timezone_rejects_out_of_range_coordinates(client):
    assert client.get("/v1/geo/timezone", params={"latitude": 91, "longitude": 0}).status_code == 422
    assert client.get("/v1/geo/timezone", params={"latitude": 0, "longitude": 181}).status_code == 422
