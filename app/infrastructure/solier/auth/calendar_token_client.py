"""Cliente HTTP dos tokens OAuth do Calendar por técnico, hospedados em `api-auth`

token OAuth não tem fallback
"""

import logging
from dataclasses import dataclass
from urllib.parse import quote

from app.exceptions import (
    InternalServiceException,
    InternalServiceNotFoundException,
    InternalServiceUpstreamException,
)
from app.infrastructure.http.internal_http_client import InternalHttpClient

_log = logging.getLogger("google_registry.solier.calendar_token_client")

STATUS_CONNECTED = "CONNECTED"
STATUS_DISCONNECTED = "DISCONNECTED"
STATUS_REVOKED = "REVOKED"

_BASE_PATH = "/internal/technicians"


@dataclass(frozen=True)
class TechnicianTokens:
    """Par de tokens OAuth do Calendar de um técnico"""

    access_token: str
    refresh_token: str
    status: str


class AuthCalendarTokenClient:
    """Consulta e atualiza, via `api-auth`, os tokens OAuth do Calendar de cada técnico"""

    def __init__(self, http_client: InternalHttpClient) -> None:
        self._http_client = http_client

    def _token_path(self, technician_id: str) -> str:
        return f"{_BASE_PATH}/{quote(technician_id, safe='')}/google-calendar-token"

    async def get(self, technician_id: str) -> TechnicianTokens | None:
        """Retorna os tokens do técnico, ou `None` se ele nunca conectou uma conta Google

        Raises:
            InternalServiceException: api-auth indisponível ou respondeu fora do contrato
        """
        try:
            response = await self._http_client.request("GET", self._token_path(technician_id))
        except InternalServiceNotFoundException:
            return None
        body = response.json()
        try:
            return TechnicianTokens(
                access_token=body["accessToken"], refresh_token=body["refreshToken"], status=body["status"]
            )
        except (KeyError, TypeError) as exc:
            raise InternalServiceUpstreamException(
                "Resposta de tokens do api-auth em formato inesperado", service="auth"
            ) from exc

    async def save(self, technician_id: str, *, access_token: str, refresh_token: str) -> None:
        """Persiste (em `api-auth`) o par de tokens do técnico

        Raises:
            InternalServiceException: falha ao gravar 
        """
        await self._http_client.request(
            "PUT",
            self._token_path(technician_id),
            json={"accessToken": access_token, "refreshToken": refresh_token},
        )

    async def disconnect(self, technician_id: str) -> None:
        """Marca a conexão do técnico como desconectada em `api-auth`
        """
        try:
            await self._http_client.request("DELETE", self._token_path(technician_id))
        except InternalServiceNotFoundException:
            _log.info("Técnico %s não tinha conexão Google registrada | desconexão é no-op", technician_id)

    async def mark_revoked(self, technician_id: str) -> None:
        """Marca a conexão do técnico como revogada em `api-auth`"""
        try:
            await self._http_client.request("PATCH", f"{self._token_path(technician_id)}/revoke", retry=True)
        except InternalServiceException:
            _log.warning("Falha ao marcar tokens do técnico %s como revogados em api-auth", technician_id)
