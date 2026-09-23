"""Endpoints de tradução automática (`/v1/i18n/...`)"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_http_client, get_internal_http_client
from app.application.i18n.service import TranslationService
from app.config import get_settings
from app.infrastructure.google.translation.adapter import TranslationAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.infrastructure.solier.persistence.translation_client import PersistenceTranslationClient
from app.schemas.i18n import TranslateRequest, TranslateResponse

router = APIRouter(prefix="/v1/i18n", tags=["i18n"])


def _get_service(
    http_client: Annotated[GoogleHttpClient, Depends(get_http_client("translation"))],
    internal_http_client: Annotated[InternalHttpClient, Depends(get_internal_http_client("persistence"))],
) -> TranslationService:
    """Monta o `TranslationService` a partir do cliente Google e do cliente de api-persistence"""
    adapter = TranslationAdapter(http_client, api_key=get_settings().google_key_translation)
    return TranslationService(adapter, PersistenceTranslationClient(internal_http_client))


@router.post("/translate", summary="Detecta o idioma de origem e traduz um registro pros demais idiomas suportados")
async def translate(
    request: TranslateRequest,
    service: Annotated[TranslationService, Depends(_get_service)],
) -> TranslateResponse:
    """Detecta o idioma de origem dos campos informados e traduz pros demais idiomas suportados (en/es/pt).

    Chamado por `api-core` logo após inserir/atualizar um registro cujos campos
    de texto entram no escopo de tradução. O resultado é gravado de volta em
    `api-core` via `PUT /internal/translations/{entityTable}/{entityId}`.

    Args:
        request: tabela/id de origem, campos de texto e idioma de origem (opcional)
        service: service com client google e client de api-persistence injetados

    Returns:
        O idioma de origem detectado e os campos traduzidos

    Raises:
        GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
    """
    return await service.translate_entity(
        request.entity_table, str(request.entity_id), request.fields, request.source_language
    )
