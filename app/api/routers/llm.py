"""Endpoints de chaves de LLM (`/v1/llm/...`)"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_llm_key_pool
from app.application.llm.key_pool import KeyPool
from app.infrastructure.llm.providers import PROVIDERS
from app.schemas.llm import AuthHeader, KeyLease, ProvidersResponse, ReportRequest

router = APIRouter(prefix="/v1/llm", tags=["llm"])


@router.get("/keys", summary="Entrega uma chave de LLM disponível")
async def lease_key(
    pool: Annotated[KeyPool, Depends(get_llm_key_pool)],
    provider: Annotated[
        Literal["gemini", "groq"] | None, Query(description="Provedor desejado (omitido: qualquer um)")
    ] = None,
    purpose: Annotated[
        Literal["chat", "vision", "embedding"] | None,
        Query(description="Uso previsto; só `embedding` restringe (provedores sem embeddings ficam de fora)"),
    ] = None,
    exclude: Annotated[
        list[str] | None, Query(description="Identificadores de chaves que o consumidor acabou de ver falhar")
    ] = None,
) -> KeyLease:
    """Entrega a próxima chave da fila de rodízio, junto com a URL base e o cabeçalho de autenticação do provedor.

    A resposta contém um segredo: não registrar em log e não repassar a terceiros. Depois de usar a chave,
    avisar o resultado em `POST /v1/llm/keys/{key_id}/report`.

    Args:
        pool: fila de chaves
        provider: provedor desejado (omitido: qualquer um)
        purpose: uso previsto
        exclude: chaves a evitar

    Returns:
        A chave, o provedor, a URL base e o cabeçalho de autenticação

    Raises:
        LlmKeysNotConfiguredException: nenhuma chave configurada para o pedido / HTTP 404
        LlmKeysUnavailableException: chaves configuradas, mas nenhuma disponível agora / HTTP 503
    """
    key = pool.lease(provider=provider, embedding=purpose == "embedding", exclude=set(exclude or []))
    provider_config = PROVIDERS[key.provider]
    return KeyLease(
        provider=key.provider,
        key_id=key.key_id,
        api_key=key.secret,
        base_url=provider_config.base_url,
        auth_header=AuthHeader(name=provider_config.auth_header_name, value=provider_config.auth_value(key.secret)),
    )


@router.post(
    "/keys/{key_id}/report", status_code=status.HTTP_204_NO_CONTENT, summary="Avisa o resultado do uso de uma chave"
)
async def report_key(
    key_id: str,
    request: ReportRequest,
    pool: Annotated[KeyPool, Depends(get_llm_key_pool)],
) -> Response:
    """Registra o resultado do uso de uma chave: `ok`, `rate_limited` (descansa) ou `invalid` (sai da fila).

    Args:
        key_id: identificador devolvido por `GET /v1/llm/keys`
        request: resultado e, em `rate_limited`, quanto esperar
        pool: fila de chaves

    Raises:
        LlmKeyNotFoundException: identificador desconhecido / HTTP 404
    """
    pool.report(key_id, request.outcome, request.retry_after_seconds)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/providers", summary="Estado das chaves de cada provedor")
async def list_providers(pool: Annotated[KeyPool, Depends(get_llm_key_pool)]) -> ProvidersResponse:
    """Estado de cada chave (disponível, descansando ou inválida), sem expor o segredo.

    Args:
        pool: fila de chaves

    Returns:
        Os provedores com chaves configuradas e o estado de cada chave
    """
    return pool.snapshot()
