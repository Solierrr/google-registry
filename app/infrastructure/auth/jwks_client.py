"""Cliente do JWK Set publicado pelo `api-auth` 

Cache por `kid` atualizado sob demanda
"""

import time
from typing import Any

import httpx

from app.config import get_settings

_MIN_REFRESH_INTERVAL_SECONDS = 10.0


class JwksClient:
    """Busca e cacheia por `kid` as chaves públicas RS256 usadas para validar o JWT de user"""

    def __init__(self) -> None:
        self._keys_by_kid: dict[str, dict[str, Any]] = {}
        self._last_refresh: float = 0.0

    async def get_key(self, kid: str) -> dict[str, Any] | None:
        """Retorna a JWK do `kid` informado, buscando o JWK Set se o `kid` ainda não for conhecido"""
        if kid not in self._keys_by_kid and self._can_refresh():
            await self._refresh()
        return self._keys_by_kid.get(kid)

    def _can_refresh(self) -> bool:
        return (time.monotonic() - self._last_refresh) >= _MIN_REFRESH_INTERVAL_SECONDS

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(get_settings().jwt_jwks_url)
            response.raise_for_status()
        keys = response.json().get("keys", [])
        self._keys_by_kid = {key["kid"]: key for key in keys if "kid" in key}
        self._last_refresh = time.monotonic()


_jwks_client = JwksClient()


def get_jwks_client() -> JwksClient:
    """Retorna a instância única do `JwksClient` do processo (cache compartilhado entre requests)."""
    return _jwks_client
