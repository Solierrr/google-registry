from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_http_client
from app.application.solar.service import SolarService
from app.config import get_settings
from app.infrastructure.google.solar.adapter import SolarAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.solar import SolarViability

router = APIRouter(prefix="/v1/solar", tags=["solar"])


def _get_service(
    http_client: Annotated[GoogleHttpClient, Depends(get_http_client("solar"))],
) -> SolarService:
    """Monta o `SolarService` a partir do cliente HTTP da capability"""
    return SolarService(SolarAdapter(http_client, api_key=get_settings().google_key_maps))


@router.get("/roof-viability", summary="Consulta a viabilidade solar do telhado mais próximo")
async def get_roof_viability(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Latitude do ponto a consultar")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Longitude do ponto a consultar")],
    service: Annotated[SolarService, Depends(_get_service)],
) -> SolarViability:
    """Consulta a viabilidade solar do telhado mais próximo da coordenada informada.

    Toda chamada consulta a Solar API do Google

    Args:
        latitude: latitude do ponto a consultar.
        longitude: longitude do ponto a consultar.
        service: service com client google injetado

    Returns:
        A viabilidade solar do telhado encontrado

    Raises:
        GoogleNotFoundException: sem dado de cobertura para a coordenada informada / HTTP 404
    """
    return await service.get_roof_viability(latitude, longitude)
