import asyncio
import logging

import httpx

from app.application.llm.key_pool import KeyPool
from app.infrastructure.llm.keys import LlmKey
from app.infrastructure.llm.providers import PROVIDERS

_log = logging.getLogger("google_registry.llm.probe")

_REJECTED_STATUS_CODES = {400, 401, 403}


async def probe_key(client: httpx.AsyncClient, key: LlmKey) -> bool | None:
    """Pergunta ao provedor se a chave é aceita

    Args:
        client: cliente HTTP
        key: chave a verificar

    Returns:
        `True` se aceita, `False` se recusada, `None` se não foi possível saber (rede, 429, 5xx)
    """
    provider = PROVIDERS[key.provider]
    try:
        response = await client.get(
            f"{provider.base_url}{provider.probe_path}",
            headers={provider.auth_header_name: provider.auth_value(key.secret)},
        )
    except httpx.HTTPError:
        return None
    if response.is_success:
        return True
    if response.status_code in _REJECTED_STATUS_CODES:
        return False
    return None


async def probe_all(client: httpx.AsyncClient, pool: KeyPool) -> None:
    """Verifica todas as chaves e atualiza o estado do pool"""
    for key in pool.keys:
        result = await probe_key(client, key)
        if result is None:
            continue
        pool.set_probe_result(key.key_id, result)
        if not result:
            _log.warning("Chave %s recusada pelo provedor %s", key.key_id, key.provider)


async def run_probes(pool: KeyPool, interval_seconds: int) -> None:
    """Verifica as chaves na subida e depois a cada `interval_seconds`, até ser cancelada"""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        while True:
            try:
                await probe_all(client, pool)
            except Exception:
                _log.exception("Falha inesperada ao verificar as chaves de LLM")
            await asyncio.sleep(interval_seconds)
