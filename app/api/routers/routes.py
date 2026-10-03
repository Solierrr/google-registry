"""Endpoints de rotas (`/v1/routes/...`)"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_http_client
from app.application.routes.service import RoutesService
from app.config import get_settings
from app.infrastructure.auth.consumer_token import require_registry_consumer
from app.infrastructure.google.routes.adapter import RoutesAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.routes import RouteRequest, RouteResponse

router = APIRouter(prefix="/v1/routes", tags=["routes"], dependencies=[Depends(require_registry_consumer)])


def _get_service(
    http_client: Annotated[GoogleHttpClient, Depends(get_http_client("routes"))],
) -> RoutesService:
    """Monta o `RoutesService` a partir do cliente HTTP da capability"""
    return RoutesService(RoutesAdapter(http_client, api_key=get_settings().google_key_maps))


@router.post("/compute", summary="Calcula rotas entre dois pontos")
async def compute_routes(
    request: RouteRequest,
    service: Annotated[RoutesService, Depends(_get_service)],
) -> RouteResponse:
    """Calcula rotas de carro ou a pé entre a origem e o destino, com alternativas.

    Toda chamada consulta a Routes API do Google. O trânsito previsto vale só para DRIVE.

    Args:
        request: origem, destino, meio de transporte e preferências
        service: service com client google injetado

    Returns:
        As rotas encontradas, com duração, distância e traçado

    Raises:
        GoogleNotFoundException: nenhuma rota entre os pontos / HTTP 404
        GoogleValidationException: horário de partida no passado ou pontos inválidos para o Google / HTTP 400
    """
    return await service.compute_routes(request)
