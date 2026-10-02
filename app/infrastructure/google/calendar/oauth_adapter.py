"""Adapter do OAuth 2.0 do Google para o Calendar (`accounts.google.com` e `oauth2.googleapis.com`)

Único lugar que conhece o formato de request/response do Google para o consentimento e os tokens
"""

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from app.domain.calendar.ports import CalendarOAuthPort, OAuthTokens, RefreshTokenRejected
from app.exceptions import GoogleProviderException, GoogleUpstreamException, GoogleValidationException
from app.infrastructure.http.google_http_client import GoogleHttpClient

_log = logging.getLogger("google_registry.calendar.oauth")

_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_PATH = "/token"
_REVOKE_PATH = "/revoke"
_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
)


@dataclass(frozen=True)
class OAuthClientConfig:
    """Credenciais do app OAuth do Calendar"""

    client_id: str
    client_secret: str
    redirect_uri: str


class CalendarOAuthAdapter(CalendarOAuthPort):
    """Implementação de `CalendarOAuthPort` sobre o OAuth 2.0 do Google"""

    def __init__(self, http_client: GoogleHttpClient, config: OAuthClientConfig) -> None:
        self._http_client = http_client
        self._config = config

    def authorization_url(self, state: str) -> str:
        """Monta a URL de consentimento com `access_type=offline` e `prompt=consent`

        Args:
            state: valor assinado que volta no callback

        Returns:
            A URL da tela de consentimento do Google
        """
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": self._config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{_AUTHORIZATION_ENDPOINT}?{query}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        """Troca o código de autorização por access e refresh token

        Args:
            code: código recebido no callback

        Returns:
            Os dois tokens

        Raises:
            GoogleValidationException: código inválido, expirado ou já usado (HTTP 400)
            GoogleUpstreamException: resposta sem `access_token` ou `refresh_token`
        """
        response = await self._http_client.request(
            "POST",
            _TOKEN_PATH,
            data={
                "code": code,
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "redirect_uri": self._config.redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        payload = _json_object(response)
        access_token, refresh_token = payload.get("access_token"), payload.get("refresh_token")
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            raise GoogleUpstreamException(
                "Resposta do OAuth do Google sem os tokens esperados", capability="calendar_oauth"
            )
        return OAuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Obtém um novo access token a partir do refresh token

        Args:
            refresh_token: refresh token do técnico

        Returns:
            O novo access token

        Raises:
            RefreshTokenRejected: o Google recusou o refresh token (`invalid_grant`)
            GoogleUpstreamException: resposta sem `access_token`
        """
        try:
            response = await self._http_client.request(
                "POST",
                _TOKEN_PATH,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "grant_type": "refresh_token",
                },
                retry=True,
            )
        except GoogleValidationException as exc:
            if exc.reason == "invalid_grant":
                raise RefreshTokenRejected from exc
            raise
        access_token = _json_object(response).get("access_token")
        if not isinstance(access_token, str):
            raise GoogleUpstreamException("Resposta do OAuth do Google sem access_token", capability="calendar_oauth")
        return access_token

    async def revoke(self, token: str) -> None:
        """Revoga o token no Google; qualquer falha é registrada e ignorada

        Args:
            token: access ou refresh token a revogar
        """
        try:
            await self._http_client.request("POST", _REVOKE_PATH, data={"token": token}, retry=True)
        except GoogleProviderException as exc:
            _log.warning("Falha ao revogar o token no Google (%s); seguindo com a desconexão", exc.error_type)


def _json_object(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleUpstreamException(
            "Resposta do OAuth do Google em formato inesperado", capability="calendar_oauth"
        ) from exc
    if not isinstance(payload, dict):
        raise GoogleUpstreamException("Resposta do OAuth do Google em formato inesperado", capability="calendar_oauth")
    return payload
