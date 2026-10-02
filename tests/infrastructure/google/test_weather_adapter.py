"""Testes de app.infrastructure.google.weather.adapter.WeatherAdapter"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.exceptions import GoogleNotFoundException, GoogleRateLimitException, GoogleUpstreamException
from app.infrastructure.google.weather.adapter import WeatherAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://weather.googleapis.com"
FORECAST_HOURS = f"{BASE_URL}/v1/forecast/hours:lookup"

NOW = datetime(2030, 1, 2, 10, 20, tzinfo=UTC)


def _hour(start: datetime, percent: int | None = 30, text: str | None = "Chuva fraca") -> dict:
    hour: dict = {
        "interval": {
            "startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endTime": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    }
    if percent is not None:
        hour["precipitation"] = {"probability": {"percent": percent, "type": "RAIN"}}
    if text is not None:
        hour["weatherCondition"] = {"description": {"text": text, "languageCode": "pt-BR"}}
    return hour


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="weather")
    yield WeatherAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_returns_the_hour_that_contains_the_instant(adapter):
    first = datetime(2030, 1, 2, 10, tzinfo=UTC)
    route = respx.get(FORECAST_HOURS).mock(
        return_value=httpx.Response(200, json={"forecastHours": [_hour(first), _hour(first + timedelta(hours=1), 80)]})
    )

    result = await adapter.get_hourly_forecast(-23.5, -46.6, NOW + timedelta(minutes=5), NOW, "pt-BR")

    assert result.interval_start == first
    assert result.interval_end == first + timedelta(hours=1)
    assert result.precipitation_probability_percent == 30
    assert result.condition == "Chuva fraca"
    request = route.calls.last.request
    assert request.headers["X-Goog-Api-Key"] == "test-key"
    assert "test-key" not in str(request.url)
    assert request.url.params["location.latitude"] == "-23.5"
    assert request.url.params["languageCode"] == "pt-BR"


@respx.mock
async def test_window_size_follows_the_distance_to_the_instant(adapter):
    route = respx.get(FORECAST_HOURS).mock(
        return_value=httpx.Response(200, json={"forecastHours": [_hour(NOW + timedelta(hours=47))]})
    )

    await adapter.get_hourly_forecast(0, 0, NOW + timedelta(hours=47, minutes=10), NOW, "pt-BR")

    assert route.calls.last.request.url.params["hours"] == "50"


@respx.mock
async def test_window_is_clamped_between_2_and_240_hours(adapter):
    route = respx.get(FORECAST_HOURS).mock(
        return_value=httpx.Response(
            200, json={"forecastHours": [_hour(NOW - timedelta(hours=1)), _hour(NOW - timedelta(minutes=20))]}
        )
    )

    await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")
    assert route.calls.last.request.url.params["hours"] == "2"

    await adapter.get_hourly_forecast(0, 0, NOW - timedelta(minutes=30), NOW, "pt-BR")
    assert route.calls.last.request.url.params["hours"] == "2"

    route.mock(return_value=httpx.Response(200, json={"forecastHours": [_hour(NOW + timedelta(hours=238))]}))
    await adapter.get_hourly_forecast(0, 0, NOW + timedelta(hours=238, minutes=30), NOW, "pt-BR")
    assert route.calls.last.request.url.params["hours"] == "240"


@respx.mock
async def test_follows_next_page_token_until_the_instant_is_found(adapter):
    target = NOW + timedelta(hours=30)
    route = respx.get(FORECAST_HOURS).mock(
        side_effect=[
            httpx.Response(200, json={"forecastHours": [_hour(NOW)], "nextPageToken": "page-2"}),
            httpx.Response(200, json={"forecastHours": [_hour(target)]}),
        ]
    )

    result = await adapter.get_hourly_forecast(0, 0, target + timedelta(minutes=1), NOW, "pt-BR")

    assert result.interval_start == target
    assert route.call_count == 2
    assert route.calls.last.request.url.params["pageToken"] == "page-2"


@respx.mock
async def test_optional_fields_are_empty_when_google_omits_them(adapter):
    respx.get(FORECAST_HOURS).mock(
        return_value=httpx.Response(200, json={"forecastHours": [_hour(NOW, percent=None, text=None)]})
    )

    result = await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")

    assert result.precipitation_probability_percent is None
    assert result.condition is None


@respx.mock
async def test_malformed_hours_are_skipped(adapter):
    payload = {"forecastHours": [{"interval": {"startTime": "x"}}, "lixo", _hour(NOW)]}
    respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(200, json=payload))

    result = await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")

    assert result.interval_start == NOW


@respx.mock
async def test_instant_not_covered_is_not_found(adapter):
    respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(200, json={"forecastHours": [_hour(NOW)]}))

    with pytest.raises(GoogleNotFoundException):
        await adapter.get_hourly_forecast(0, 0, NOW + timedelta(hours=5), NOW, "pt-BR")


@respx.mock
async def test_stops_after_ten_pages(adapter):
    route = respx.get(FORECAST_HOURS).mock(
        return_value=httpx.Response(200, json={"forecastHours": [], "nextPageToken": "more"})
    )

    with pytest.raises(GoogleNotFoundException):
        await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")

    assert route.call_count == 10


@respx.mock
@pytest.mark.parametrize("response", [httpx.Response(200, content=b"<html>"), httpx.Response(200, json=["lista"])])
async def test_unexpected_payload_is_upstream_error(adapter, response):
    respx.get(FORECAST_HOURS).mock(return_value=response)

    with pytest.raises(GoogleUpstreamException):
        await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")


@respx.mock
async def test_rate_limit_is_retried_then_raised(adapter):
    route = respx.get(FORECAST_HOURS).mock(return_value=httpx.Response(429))

    with pytest.raises(GoogleRateLimitException):
        await adapter.get_hourly_forecast(0, 0, NOW, NOW, "pt-BR")

    assert route.call_count == 3
