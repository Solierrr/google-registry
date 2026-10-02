"""Endpoints de endereço (`/v1/address/...`)"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_http_client
from app.application.address.service import AddressService
from app.config import get_settings
from app.infrastructure.google.places.adapter import PlacesAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import Address, SuggestionsRequest, SuggestionsResponse

router = APIRouter(prefix="/v1/address", tags=["address"])


def _get_service(
    places_client: Annotated[GoogleHttpClient, Depends(get_http_client("places"))],
) -> AddressService:
    """Monta o `AddressService` a partir dos clientes Google das capabilities de endereço"""
    api_key = get_settings().google_key_maps
    return AddressService(PlacesAdapter(places_client, api_key=api_key))


@router.post("/suggestions", summary="Sugere endereços enquanto o usuário digita")
async def suggest_addresses(
    request: SuggestionsRequest,
    service: Annotated[AddressService, Depends(_get_service)],
) -> SuggestionsResponse:
    """Sugere endereços para o texto digitado, restritos ao país informado (padrão BR).

    Args:
        request: texto, token de sessão (opcional), idioma e país
        service: service com os clients google injetados

    Returns:
        As sugestões, da mais relevante para a menos (lista vazia se nada casar)

    Raises:
        GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
    """
    return await service.suggest(
        request.query, session_token=request.session_token, language=request.language, country=request.country
    )


@router.get("/places/{place_id}", summary="Detalha o endereço de um lugar escolhido nas sugestões")
async def get_place(
    place_id: str,
    service: Annotated[AddressService, Depends(_get_service)],
    session_token: Annotated[
        str | None, Query(description="Mesmo token de sessão enviado nas sugestões (agrupa a cobrança)")
    ] = None,
    language: Annotated[str, Query(description="Idioma da resposta")] = "pt-BR",
) -> Address:
    """Devolve o endereço estruturado e as coordenadas de um lugar.

    Args:
        place_id: identificador do lugar, vindo das sugestões
        service: service com os clients google injetados
        session_token: mesmo token de sessão enviado nas sugestões
        language: idioma da resposta

    Returns:
        O endereço com coordenadas

    Raises:
        GoogleNotFoundException: place_id inexistente ou expirado / HTTP 404
    """
    return await service.get_place(place_id, session_token=session_token, language=language)
