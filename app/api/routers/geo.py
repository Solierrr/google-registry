"""Endpoints de geo (`/v1/geo/...`)"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.geo.service import GeoService
from app.infrastructure.geo.timezone import TzfpyTimezoneFinder
from app.schemas.geo import TimezoneResponse

router = APIRouter(prefix="/v1/geo", tags=["geo"])


def _get_service() -> GeoService:
    """Monta o `GeoService` com a base de fusos local"""
    return GeoService(TzfpyTimezoneFinder())


@router.get("/timezone", summary="Fuso horário de uma coordenada")
async def get_timezone(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Latitude do ponto")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Longitude do ponto")],
    service: Annotated[GeoService, Depends(_get_service)],
    at: Annotated[
        datetime | None,
        Query(description="Instante para calcular o deslocamento do UTC (ISO 8601; omitido: agora; sem fuso vale UTC)"),
    ] = None,
) -> TimezoneResponse:
    """Descobre o fuso horário da coordenada sem consultar nenhuma API externa.

    Args:
        latitude: latitude do ponto
        longitude: longitude do ponto
        service: service com a base de fusos local
        at: instante para calcular o deslocamento do UTC

    Returns:
        O identificador IANA do fuso e o deslocamento do UTC em segundos

    Raises:
        HTTPException: 404 se não for possível determinar o fuso
    """
    result = service.get_timezone(latitude, longitude, at)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não foi possível determinar o fuso horário da coordenada")
    return result
