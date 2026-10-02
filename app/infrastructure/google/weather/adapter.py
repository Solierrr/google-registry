"""Adapter da Weather API do Google (`forecast/hours:lookup`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

import math
from datetime import UTC, datetime
from typing import Any

from app.domain.weather.ports import WeatherPort
from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.weather import HourlyWeather

_FORECAST_HOURS_PATH = "/v1/forecast/hours:lookup"
_PAGE_SIZE = 24
_MAX_HOURS = 240
_MAX_PAGES = 10


class WeatherAdapter(WeatherPort):
    """Implementação de `WeatherPort` sobre a Weather API do Google (`forecast.hours.lookup`)"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def get_hourly_forecast(
        self, latitude: float, longitude: float, at: datetime, now: datetime, language: str
    ) -> HourlyWeather:
        """Percorre as páginas de `forecast/hours:lookup` até achar a hora que contém `at`

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            at: instante consultado (com fuso)
            now: instante atual (com fuso), usado para dimensionar a janela pedida ao Google
            language: idioma da descrição da condição (BCP 47)

        Returns:
            A previsão da hora que contém `at`

        Raises:
            GoogleNotFoundException: nenhuma hora devolvida pelo Google contém `at`
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        hours_ahead = math.ceil((at - now).total_seconds() / 3600) + 2
        params: dict[str, Any] = {
            "location.latitude": latitude,
            "location.longitude": longitude,
            "hours": min(_MAX_HOURS, max(2, hours_ahead)),
            "pageSize": _PAGE_SIZE,
            "languageCode": language,
        }

        for _ in range(_MAX_PAGES):
            response = await self._http_client.request(
                "GET", _FORECAST_HOURS_PATH, params=params, headers={"X-Goog-Api-Key": self._api_key}
            )
            try:
                payload = response.json()
            except ValueError as exc:
                raise _unexpected_format() from exc
            if not isinstance(payload, dict):
                raise _unexpected_format()

            forecast = _find_hour(payload.get("forecastHours", []), at)
            if forecast is not None:
                return forecast
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token

        raise GoogleNotFoundException("Sem previsão do clima para o instante informado", capability="weather")


def _unexpected_format() -> GoogleUpstreamException:
    return GoogleUpstreamException("Resposta da Weather API do Google em formato inesperado", capability="weather")


def _find_hour(raw_hours: Any, at: datetime) -> HourlyWeather | None:
    """Procura, entre as horas de uma página, a que contém `at`, descartando as malformadas

    Args:
        raw_hours: lista `forecastHours` do payload do Google
        at: instante consultado (com fuso)

    Returns:
        A previsão da hora, ou `None` se nenhuma das horas contém `at`
    """
    if not isinstance(raw_hours, list):
        return None
    for raw in raw_hours:
        try:
            start = _parse_time(raw["interval"]["startTime"])
            end = _parse_time(raw["interval"]["endTime"])
        except KeyError, TypeError, ValueError:
            continue
        if start <= at < end:
            return _to_hourly_weather(raw, start, end)
    return None


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _to_hourly_weather(raw: dict[str, Any], start: datetime, end: datetime) -> HourlyWeather:
    precipitation = raw.get("precipitation")
    probability = precipitation.get("probability") if isinstance(precipitation, dict) else None
    percent = probability.get("percent") if isinstance(probability, dict) else None
    condition = raw.get("weatherCondition")
    description = condition.get("description") if isinstance(condition, dict) else None
    text = description.get("text") if isinstance(description, dict) else None
    return HourlyWeather(
        interval_start=start,
        interval_end=end,
        precipitation_probability_percent=int(percent) if isinstance(percent, int | float) else None,
        condition=text if isinstance(text, str) else None,
    )
