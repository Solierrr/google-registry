"""Testes de GET /v1/weather/hourly"""

from datetime import UTC, datetime, timedelta

import httpx
import respx

FORECAST_HOURS = "https://weather.googleapis.com/v1/forecast/hours:lookup"


def _payload(start: datetime) -> dict:
    return {
        "forecastHours": [
            {
                "interval": {
                    "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "endTime": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "precipitation": {"probability": {"percent": 40}},
                "weatherCondition": {"description": {"text": "Nublado"}},
            }
        ]
    }


@respx.mock
def test_hourly_returns_the_current_hour_by_default(client):
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(200, json=_payload(start)))

    response = client.get("/v1/weather/hourly", params={"latitude": -23.5, "longitude": -46.6})

    assert response.status_code == 200
    body = response.json()
    assert body["precipitation_probability_percent"] == 40
    assert body["condition"] == "Nublado"


@respx.mock
def test_hourly_uses_the_requested_instant_and_language(client):
    target = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=5)
    route = respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(200, json=_payload(target)))

    response = client.get(
        "/v1/weather/hourly",
        params={
            "latitude": -23.5,
            "longitude": -46.6,
            "at": (target + timedelta(minutes=10)).isoformat(),
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert route.calls.last.request.url.params["languageCode"] == "en"


def test_hourly_rejects_an_instant_outside_the_window(client):
    far = datetime.now(UTC) + timedelta(days=30)

    response = client.get("/v1/weather/hourly", params={"latitude": -23.5, "longitude": -46.6, "at": far.isoformat()})

    assert response.status_code == 422


def test_hourly_rejects_out_of_range_latitude(client):
    response = client.get("/v1/weather/hourly", params={"latitude": 100, "longitude": 0})

    assert response.status_code == 422


@respx.mock
def test_hourly_returns_404_when_google_has_no_forecast_for_the_instant(client):
    far_hour = datetime.now(UTC) + timedelta(hours=100)
    respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(200, json=_payload(far_hour)))

    response = client.get("/v1/weather/hourly", params={"latitude": -23.5, "longitude": -46.6})

    assert response.status_code == 404
    assert response.json()["code"] == "GoogleNotFoundException"
