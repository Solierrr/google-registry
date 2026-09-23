"""Endpoints de viabilidade solar (`/v1/solar/...`)"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_http_client, get_persistence_unit_client
from app.application.solar.service import SolarService
from app.config import get_settings
from app.infrastructure.google.solar.adapter import SolarAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.solier.persistence.unit_client import PersistenceUnitClient
from app.schemas.solar import SolarViability

router = APIRouter(prefix="/v1/solar", tags=["solar"])


def _get_service(
    http_client: Annotated[GoogleHttpClient, Depends(get_http_client("solar"))],
    unit_client: Annotated[PersistenceUnitClient, Depends(get_persistence_unit_client)],
) -> SolarService:
    """Monta o `SolarService` a partir do cliente HTTP da capability e dos clientes de api-persistence"""
    return SolarService(SolarAdapter(http_client, api_key=get_settings().google_key_maps), unit_client)


@router.get("/roof-viability", summary="Consulta a viabilidade solar do telhado mais próximo")
async def get_roof_viability(
    latitude: Annotated[float, Query(ge=-90, le=90, description="Latitude do ponto a consultar")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Longitude do ponto a consultar")],
    service: Annotated[SolarService, Depends(_get_service)],
    unit_id: Annotated[
        UUID | None, Query(description="Se informado, grava o resultado como perfil solar dessa unidade")
    ] = None,
) -> SolarViability:
    """Consulta a viabilidade solar do telhado mais próximo da coordenada informada.

    Toda chamada consulta a Solar API do Google
    Com `unit_id`, o resultado também é gravado como perfil solar da unidade em api-persistence

    Args:
        latitude: latitude do ponto a consultar.
        longitude: longitude do ponto a consultar.
        service: service com client google e adapter injetados
        unit_id: se informado, grava o resultado como perfil solar dessa `LocalUnit` real

    Returns:
        A viabilidade solar do telhado encontrado

    Raises:
        GoogleNotFoundException: sem dado de cobertura para a coordenada informada / HTTP 404
    """
    return await service.get_roof_viability(latitude, longitude, str(unit_id) if unit_id else None)
