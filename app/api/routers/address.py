"""Endpoints de endereço (`/v1/address/...`)"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_http_client
from app.application.address.service import AddressService
from app.config import get_settings
from app.infrastructure.auth.consumer_token import require_registry_consumer
from app.infrastructure.google.address_validation.adapter import AddressValidationAdapter
from app.infrastructure.google.geocoding.adapter import GeocodingAdapter
from app.infrastructure.google.places.adapter import PlacesAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import (
    Address,
    AddressListResponse,
    GeocodeRequest,
    ResolveRequest,
    ResolveResponse,
    ReverseGeocodeRequest,
    SuggestionsRequest,
    SuggestionsResponse,
    ValidateRequest,
    ValidateResponse,
)

router = APIRouter(prefix="/v1/address", tags=["address"], dependencies=[Depends(require_registry_consumer)])


def _get_service(
    places_client: Annotated[GoogleHttpClient, Depends(get_http_client("places"))],
    geocoding_client: Annotated[GoogleHttpClient, Depends(get_http_client("geocoding"))],
    validation_client: Annotated[GoogleHttpClient, Depends(get_http_client("address_validation"))],
) -> AddressService:
    """Monta o `AddressService` a partir dos clientes Google das capabilities de endereço"""
    api_key = get_settings().google_key_maps
    return AddressService(
        PlacesAdapter(places_client, api_key=api_key),
        GeocodingAdapter(geocoding_client, api_key=api_key),
        AddressValidationAdapter(validation_client, api_key=api_key),
    )


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


@router.post("/geocode", summary="Converte um endereço em texto em coordenadas")
async def geocode(
    request: GeocodeRequest,
    service: Annotated[AddressService, Depends(_get_service)],
) -> AddressListResponse:
    """Converte um endereço em texto livre em coordenadas, restrito ao Brasil.

    Args:
        request: endereço e idioma
        service: service com os clients google injetados

    Returns:
        Os endereços encontrados, com precisão e indicação de casamento parcial (lista vazia se nada casar)

    Raises:
        GoogleRateLimitException: quota excedida / HTTP 503
        GoogleValidationException: pedido inválido / HTTP 400
    """
    return await service.geocode(request.address, language=request.language)


@router.post("/reverse-geocode", summary="Converte uma coordenada em endereços")
async def reverse_geocode(
    request: ReverseGeocodeRequest,
    service: Annotated[AddressService, Depends(_get_service)],
) -> AddressListResponse:
    """Converte uma coordenada em endereços, do mais específico para o menos.

    Args:
        request: coordenada e idioma
        service: service com os clients google injetados

    Returns:
        Os endereços encontrados (lista vazia se não houver)

    Raises:
        GoogleRateLimitException: quota excedida / HTTP 503
        GoogleValidationException: pedido inválido / HTTP 400
    """
    return await service.reverse_geocode(request.latitude, request.longitude, language=request.language)


@router.post("/validate", summary="Valida e normaliza um endereço digitado à mão")
async def validate_address(
    request: ValidateRequest,
    service: Annotated[AddressService, Depends(_get_service)],
) -> ValidateResponse:
    """Valida um endereço e devolve o veredito, o que falta ou não foi confirmado e a versão normalizada.

    Args:
        request: linhas do endereço, CEP, cidade, UF e país
        service: service com os clients google injetados

    Returns:
        O veredito (`ok`, `needs_review` ou `invalid`) e o endereço normalizado com coordenadas

    Raises:
        GoogleValidationException: pedido inválido / HTTP 400
    """
    return await service.validate(request)


@router.post("/resolve", summary="Resolve o endereço final de um lugar escolhido ou de um texto")
async def resolve_address(
    request: ResolveRequest,
    service: Annotated[AddressService, Depends(_get_service)],
) -> ResolveResponse:
    """Devolve o endereço estruturado, as coordenadas e a validação em uma só chamada.

    Informe `place_id` (lugar escolhido nas sugestões) ou `query` (texto livre), nunca os dois.
    Se a validação falhar por erro do Google, o endereço ainda é devolvido, com `validation` nulo.

    Args:
        request: `place_id` ou `query`, token de sessão e idioma
        service: service com os clients google injetados

    Returns:
        O endereço com coordenadas e a validação

    Raises:
        GoogleNotFoundException: lugar ou texto sem resultado / HTTP 404
    """
    return await service.resolve(
        place_id=request.place_id,
        query=request.query,
        session_token=request.session_token,
        language=request.language,
    )
