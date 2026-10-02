"""Contratos da capability de Calendar esperados"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.calendar import Event, EventCreate, EventList, EventUpdate, Interval


class RefreshTokenRejected(Exception):
    """O Google recusou o refresh token (`invalid_grant`): o técnico revogou o acesso ou o token expirou"""


@dataclass(frozen=True)
class OAuthTokens:
    """Tokens devolvidos pela troca do código de autorização"""

    access_token: str
    refresh_token: str


class CalendarApiPort(Protocol):
    """Operações da Calendar API esperadas, sempre na agenda principal do técnico"""

    async def free_busy(self, access_token: str, start: datetime, end: datetime) -> list[Interval]:
        """Intervalos ocupados no período

        Raises:
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
        """
        ...

    async def create_event(self, access_token: str, event: EventCreate) -> Event:
        """Cria um evento (não é idempotente: sem retry)"""
        ...

    async def list_events(self, access_token: str, start: datetime, end: datetime, page_token: str | None) -> EventList:
        """Lista os eventos do período, expandindo recorrências e ordenando por início"""
        ...

    async def update_event(self, access_token: str, event_id: str, update: EventUpdate) -> Event:
        """Atualiza só os campos enviados

        Raises:
            GoogleNotFoundException: evento inexistente
        """
        ...

    async def delete_event(self, access_token: str, event_id: str) -> None:
        """Apaga o evento; evento já inexistente não é erro"""
        ...


class CalendarOAuthPort(Protocol):
    """Operações do OAuth 2.0 do Google esperadas"""

    def authorization_url(self, state: str) -> str:
        """Endereço da tela de consentimento, com acesso offline e consentimento explícito"""
        ...

    async def exchange_code(self, code: str) -> OAuthTokens:
        """Troca o código de autorização por tokens

        Raises:
            GoogleValidationException: código inválido, expirado ou já usado (HTTP 400)
            GoogleUpstreamException: resposta sem `refresh_token`
        """
        ...

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Obtém um novo access token

        Raises:
            RefreshTokenRejected: o Google recusou o refresh token (`invalid_grant`)
        """
        ...

    async def revoke(self, token: str) -> None:
        """Revoga o token no Google; falha é tolerada"""
        ...
