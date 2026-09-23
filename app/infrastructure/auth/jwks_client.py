"""Cliente do JWK Set publicado pelo `api-auth`

Cache por `kid` atualizado sob demanda
"""

import logging
import time
from typing import Any

import httpx

from app.config import get_settings

_MIN_REFRESH_INTERVAL_SECONDS = 10.0
_MAX_KEYSET_AGE_SECONDS = 300.0

_log = logging.getLogger("google_registry.auth.jwks")


class JwksUnavailableError(Exception):
    """O JWK Set não pôde ser obtido e o `kid` do token não está em cache"""


class JwksClient:
    """Busca e cacheia por `kid` as chaves públicas RS256 usadas para validar o JWT de user"""

    def __init__(self) -> None:
        self._keys_by_kid: dict[str, dict[str, Any]] = {}
        self._last_refresh: float = float("-inf")
        self._last_refresh_failed = False

    async def get_key(self, kid: str) -> dict[str, Any] | None:
        """Retorna a JWK do `kid`, buscando o JWK Set se o `kid` for desconhecido ou o cache venceu

        Raises:
            JwksUnavailableError: o `kid` não está em cache e a busca ao api-auth falhou
        """
        if (kid not in self._keys_by_kid or self._is_stale()) and self._can_refresh():
            await self._refresh()
        key = self._keys_by_kid.get(kid)
        if key is None and self._last_refresh_failed:
            raise JwksUnavailableError("JWK indisponível no api-auth")
        return key

    def _can_refresh(self) -> bool:
        return (time.monotonic() - self._last_refresh) >= _MIN_REFRESH_INTERVAL_SECONDS

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._last_refresh) >= _MAX_KEYSET_AGE_SECONDS

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(get_settings().jwt_jwks_url)
                response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("JWK Set deveria ser um objeto JSON")
            keys = payload.get("keys", [])
            self._keys_by_kid = {key["kid"]: key for key in keys if "kid" in key}
            self._last_refresh_failed = False
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            self._last_refresh_failed = True
            _log.warning("Falha ao buscar o JWK Set do api-auth: %s", exc)
        finally:
            self._last_refresh = time.monotonic()


_jwks_client = JwksClient()


def get_jwks_client() -> JwksClient:
    """Retorna a instância única do `JwksClient` do processo (cache compartilhado entre requests)."""
    return _jwks_client
