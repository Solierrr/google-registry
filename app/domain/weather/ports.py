"""Contrato da capability de clima esperado"""

from datetime import datetime
from typing import Protocol

from app.schemas.weather import HourlyWeather


class WeatherPort(Protocol):
    """Operações de clima esperadas"""

    async def get_hourly_forecast(
        self, latitude: float, longitude: float, at: datetime, now: datetime, language: str
    ) -> HourlyWeather:
        """Busca a previsão da hora que contém `at`

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            at: instante consultado (com fuso)
            now: instante atual (com fuso), usado para dimensionar a janela pedida ao Google
            language: idioma da descrição da condição (BCP 47)

        Returns:
            A previsão da hora que contém `at`

        Raises:
            GoogleNotFoundException: o Google não devolveu previsão para o instante
        """
        ...
