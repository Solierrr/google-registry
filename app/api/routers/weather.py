"""Endpoints de clima (`/v1/weather/...`)"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_http_client
from app.application.weather.service import ForecastWindowError, WeatherService
from app.config import get_settings
from app.infrastructure.auth.consumer_token import require_registry_consumer
from app.infrastructure.google.weather.adapter import WeatherAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.weather import HourlyWeather

router = APIRouter(prefix="/v1/weather", tags=["weather"], dependencies=[Depends(require_registry_consumer)])


def _get_service(
    http_client: Annotated[GoogleHttpClient, Depends(get_http_client("weather"))],
) -> WeatherService:
    """Monta o `WeatherService` a partir do cliente HTTP da capability"""
    return WeatherService(WeatherAdapter(http_client, api_key=get_settings().google_key_maps))


@router.get("/hourly", summary="Previsão do clima para uma hora")
async def get_hourly_weather(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Latitude do ponto")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Longitude do ponto")],
    service: Annotated[WeatherService, Depends(_get_service)],
    at: Annotated[
        datetime | None,
        Query(
            description=(
                "Instante da previsão (ISO 8601; omitido: agora; sem fuso vale UTC). "
                "Aceita de 1 hora atrás até 239 horas à frente"
            )
        ),
    ] = None,
    language: Annotated[str, Query(description="Idioma da descrição da condição (BCP 47)")] = "pt-BR",
) -> HourlyWeather:
    """Devolve a previsão da hora que contém o instante informado, para a coordenada.

    Toda chamada consulta a Weather API do Google

    Args:
        latitude: latitude do ponto
        longitude: longitude do ponto
        service: service com client google injetado
        at: instante da previsão
        language: idioma da descrição da condição

    Returns:
        O intervalo da hora, a probabilidade de precipitação e a condição do tempo

    Raises:
        HTTPException: 422 se `at` estiver fora da janela de previsão horária
        GoogleNotFoundException: o Google não devolveu previsão para o instante / HTTP 404
    """
    try:
        return await service.get_hourly_forecast(latitude, longitude, at, language)
    except ForecastWindowError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
