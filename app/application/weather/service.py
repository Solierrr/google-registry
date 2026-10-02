"""Serviço de aplicação da capability de clima

Valida a janela de previsão e orquestra o `WeatherPort`
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.domain.weather.ports import WeatherPort
from app.schemas.weather import HourlyWeather

_PAST_TOLERANCE = timedelta(hours=1)
_MAX_AHEAD = timedelta(hours=239)


class ForecastWindowError(ValueError):
    """O instante consultado está fora da janela de previsão horária do Google"""


class WeatherService:
    """Orquestra o provedor Google (`WeatherPort`)"""

    def __init__(self, port: WeatherPort, clock: Callable[[], datetime] | None = None) -> None:
        self._port = port
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_hourly_forecast(
        self, latitude: float, longitude: float, at: datetime | None, language: str
    ) -> HourlyWeather:
        """Busca a previsão da hora que contém `at`

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            at: instante consultado (sem fuso vale UTC; omitido: agora)
            language: idioma da descrição da condição (BCP 47)

        Returns:
            A previsão da hora que contém `at`

        Raises:
            ForecastWindowError: `at` fora da janela de previsão horária do Google (de 1 hora atrás até 239 horas à frente)
            GoogleNotFoundException: o Google não devolveu previsão para o instante
        """
        now = self._clock()
        instant = now if at is None else (at.replace(tzinfo=UTC) if at.tzinfo is None else at.astimezone(UTC))
        if instant < now - _PAST_TOLERANCE or instant > now + _MAX_AHEAD:
            raise ForecastWindowError("O instante precisa estar entre 1 hora atrás e 239 horas à frente")
        return await self._port.get_hourly_forecast(latitude, longitude, instant, now, language)
