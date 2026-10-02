"""Testes de app.application.weather.service.WeatherService"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.application.weather.service import ForecastWindowError, WeatherService
from app.schemas.weather import HourlyWeather

NOW = datetime(2030, 1, 2, 10, 20, tzinfo=UTC)


class FakePort:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def get_hourly_forecast(self, latitude, longitude, at, now, language) -> HourlyWeather:
        self.calls.append((latitude, longitude, at, now, language))
        return HourlyWeather(interval_start=at, interval_end=at + timedelta(hours=1))


@pytest.fixture
def port() -> FakePort:
    return FakePort()


@pytest.fixture
def service(port) -> WeatherService:
    return WeatherService(port, clock=lambda: NOW)


async def test_omitted_instant_means_now(service, port):
    await service.get_hourly_forecast(1.0, 2.0, None, "pt-BR")

    assert port.calls == [(1.0, 2.0, NOW, NOW, "pt-BR")]


async def test_naive_instant_is_taken_as_utc(service, port):
    await service.get_hourly_forecast(1.0, 2.0, datetime(2030, 1, 2, 12, 0), "en")

    assert port.calls[0][2] == datetime(2030, 1, 2, 12, 0, tzinfo=UTC)


async def test_instant_with_offset_is_converted_to_utc(service, port):
    local = datetime(2030, 1, 2, 9, 0, tzinfo=timezone(timedelta(hours=-3)))

    await service.get_hourly_forecast(1.0, 2.0, local, "pt-BR")

    assert port.calls[0][2] == datetime(2030, 1, 2, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("delta", [timedelta(hours=-1), timedelta(hours=239)])
async def test_window_limits_are_accepted(service, delta):
    result = await service.get_hourly_forecast(0.0, 0.0, NOW + delta, "pt-BR")

    assert result.interval_start == NOW + delta


@pytest.mark.parametrize("delta", [timedelta(hours=-1, seconds=-1), timedelta(hours=239, seconds=1)])
async def test_outside_the_window_is_rejected_without_calling_google(service, port, delta):
    with pytest.raises(ForecastWindowError):
        await service.get_hourly_forecast(0.0, 0.0, NOW + delta, "pt-BR")

    assert port.calls == []


async def test_default_clock_uses_the_current_time():
    port = FakePort()

    await WeatherService(port).get_hourly_forecast(0.0, 0.0, None, "pt-BR")

    assert abs(port.calls[0][3] - datetime.now(UTC)) < timedelta(seconds=5)
