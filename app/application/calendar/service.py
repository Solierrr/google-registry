"""Serviço de aplicação da capability de Calendar

Orquestra o consentimento OAuth, os tokens do técnico (guardados no `api-auth`) e a Calendar API.
O registry não guarda nada: o par de tokens vive no `api-auth`
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar

from app.domain.calendar.ports import CalendarApiPort, CalendarOAuthPort, RefreshTokenRejected
from app.exceptions import (
    CalendarConsentDeniedException,
    CalendarNotConfiguredException,
    CalendarTokenRevokedException,
    GoogleAuthenticationException,
    GoogleNotFoundException,
    GoogleValidationException,
)
from app.infrastructure.calendar.state import CalendarStateSigner, InvalidStateError
from app.infrastructure.solier.auth.calendar_token_client import (
    STATUS_CONNECTED,
    AuthCalendarTokenClient,
    TechnicianTokens,
)
from app.schemas.calendar import (
    Availability,
    ConnectionStatus,
    ConnectResponse,
    Event,
    EventCreate,
    EventList,
    EventUpdate,
    Interval,
)

_log = logging.getLogger("google_registry.calendar")

_MAX_PERIOD = timedelta(days=60)
_CONSENT_DENIED = "access_denied"
_UNAUTHORIZED = 401

T = TypeVar("T")


class InvalidPeriodError(ValueError):
    """Período de consulta inválido (fim antes do início ou maior que o máximo permitido)"""


class CalendarService:
    """Orquestra os provedores Google (`CalendarApiPort`, `CalendarOAuthPort`) e os tokens do `api-auth`"""

    def __init__(
        self,
        api: CalendarApiPort,
        oauth: CalendarOAuthPort | None,
        tokens: AuthCalendarTokenClient,
        signer: CalendarStateSigner | None,
    ) -> None:
        self._api = api
        self._oauth = oauth
        self._tokens = tokens
        self._signer = signer

    def connect(self, technician_id: str) -> ConnectResponse:
        """Monta o endereço da tela de consentimento do Google para o técnico

        Args:
            technician_id: técnico que vai conectar a conta Google

        Returns:
            A URL de consentimento, com um `state` assinado de validade curta

        Raises:
            CalendarNotConfiguredException: OAuth do Calendar não configurado neste ambiente
        """
        oauth, signer = self._require_oauth(), self._require_signer()
        return ConnectResponse(authorization_url=oauth.authorization_url(signer.sign(technician_id)))

    async def complete_connection(self, code: str | None, state: str, error: str | None) -> ConnectionStatus:
        """Conclui o consentimento: troca o código por tokens e os grava no `api-auth`

        Args:
            code: código de autorização do Google
            state: `state` devolvido pelo Google
            error: erro informado pelo Google no lugar do código (ex.: `access_denied`)

        Returns:
            `connected` quando os tokens foram gravados

        Raises:
            CalendarNotConfiguredException: OAuth do Calendar não configurado neste ambiente
            GoogleValidationException: `state` inválido ou expirado, ou sem `code` nem `error`
            CalendarConsentDeniedException: o técnico recusou o consentimento (nada é gravado)
        """
        oauth, signer = self._require_oauth(), self._require_signer()
        try:
            technician_id = signer.verify(state)
        except InvalidStateError as exc:
            raise GoogleValidationException(
                "state inválido ou expirado", capability="calendar", reason="invalid_state"
            ) from exc
        if error is not None:
            if error == _CONSENT_DENIED:
                raise CalendarConsentDeniedException(
                    "O técnico não autorizou o acesso ao Calendar", technician_id=technician_id
                )
            raise GoogleValidationException(
                "O Google devolveu erro no consentimento", capability="calendar", reason=error
            )
        if not code:
            raise GoogleValidationException("Callback sem code", capability="calendar", reason="missing_code")

        tokens = await oauth.exchange_code(code)
        await self._tokens.save(technician_id, access_token=tokens.access_token, refresh_token=tokens.refresh_token)
        return ConnectionStatus(status="connected")

    async def disconnect(self, technician_id: str) -> None:
        """Revoga o acesso no Google (falha tolerada) e marca a conexão como desconectada no `api-auth`

        Args:
            technician_id: técnico a desconectar; sem conexão não é erro
        """
        tokens = await self._tokens.get(technician_id)
        if tokens is not None and self._oauth is not None:
            await self._oauth.revoke(tokens.refresh_token)
        await self._tokens.disconnect(technician_id)

    async def get_availability(self, technician_id: str, start: datetime, end: datetime) -> Availability:
        """Intervalos ocupados e janelas livres do técnico no período

        Args:
            technician_id: técnico consultado
            start: início do período
            end: fim do período (no máximo 60 dias depois do início)

        Returns:
            Os intervalos ocupados e as janelas livres dentro do período

        Raises:
            InvalidPeriodError: `start >= end` ou período maior que 60 dias
            GoogleNotFoundException: técnico não conectado
            CalendarTokenRevokedException: o técnico revogou o acesso
        """
        _validate_period(start, end)
        busy = await self._call(technician_id, lambda token: self._api.free_busy(token, start, end))
        return Availability(busy=busy, free=_free_windows(busy, start, end))

    async def create_event(self, technician_id: str, event: EventCreate) -> Event:
        """Cria um evento na agenda principal do técnico

        Raises:
            GoogleNotFoundException: técnico não conectado
            CalendarTokenRevokedException: o técnico revogou o acesso
        """
        return await self._call(technician_id, lambda token: self._api.create_event(token, event))

    async def list_events(
        self, technician_id: str, start: datetime, end: datetime, page_token: str | None
    ) -> EventList:
        """Lista os eventos do técnico no período

        Raises:
            InvalidPeriodError: `start >= end` ou período maior que 60 dias
            GoogleNotFoundException: técnico não conectado
            CalendarTokenRevokedException: o técnico revogou o acesso
        """
        _validate_period(start, end)
        return await self._call(technician_id, lambda token: self._api.list_events(token, start, end, page_token))

    async def update_event(self, technician_id: str, event_id: str, update: EventUpdate) -> Event:
        """Atualiza só os campos enviados de um evento do técnico

        Raises:
            GoogleNotFoundException: técnico não conectado ou evento inexistente
            CalendarTokenRevokedException: o técnico revogou o acesso
        """
        return await self._call(technician_id, lambda token: self._api.update_event(token, event_id, update))

    async def delete_event(self, technician_id: str, event_id: str) -> None:
        """Apaga um evento do técnico; evento inexistente não é erro

        Raises:
            GoogleNotFoundException: técnico não conectado
            CalendarTokenRevokedException: o técnico revogou o acesso
        """
        await self._call(technician_id, lambda token: self._api.delete_event(token, event_id))

    async def _call(self, technician_id: str, operation: Callable[[str], Awaitable[T]]) -> T:
        """Executa `operation` com o access token do técnico, renovando-o uma vez se o Google devolver 401"""
        tokens = await self._tokens.get(technician_id)
        if tokens is None or tokens.status != STATUS_CONNECTED:
            raise GoogleNotFoundException("Técnico não conectado ao Google Calendar", capability="calendar")
        try:
            return await operation(tokens.access_token)
        except GoogleAuthenticationException as exc:
            if exc.status_code != _UNAUTHORIZED:
                raise
        access_token = await self._renew_access_token(technician_id, tokens)
        return await operation(access_token)

    async def _renew_access_token(self, technician_id: str, tokens: TechnicianTokens) -> str:
        oauth = self._require_oauth()
        try:
            access_token = await oauth.refresh_access_token(tokens.refresh_token)
        except RefreshTokenRejected as exc:
            await self._tokens.mark_revoked(technician_id)
            raise CalendarTokenRevokedException(
                "O técnico revogou o acesso ao Google Calendar", technician_id=technician_id
            ) from exc
        await self._tokens.save(technician_id, access_token=access_token, refresh_token=tokens.refresh_token)
        return access_token

    def _require_oauth(self) -> CalendarOAuthPort:
        if self._oauth is None:
            raise CalendarNotConfiguredException(
                "OAuth do Google Calendar não configurado neste ambiente", capability="calendar"
            )
        return self._oauth

    def _require_signer(self) -> CalendarStateSigner:
        if self._signer is None:
            raise CalendarNotConfiguredException(
                "CALENDAR_STATE_SECRET não configurado neste ambiente", capability="calendar"
            )
        return self._signer


def _validate_period(start: datetime, end: datetime) -> None:
    if start >= end:
        raise InvalidPeriodError("from precisa ser anterior a to")
    if end - start > _MAX_PERIOD:
        raise InvalidPeriodError("o período máximo é de 60 dias")


def _free_windows(busy: list[Interval], start: datetime, end: datetime) -> list[Interval]:
    """Janelas livres dentro de `[start, end]`: o que sobra depois de unir os intervalos ocupados"""
    merged: list[tuple[datetime, datetime]] = []
    for interval in sorted(busy, key=lambda item: item.start):
        busy_start, busy_end = max(interval.start, start), min(interval.end, end)
        if busy_start >= busy_end:
            continue
        if merged and busy_start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], busy_end))
        else:
            merged.append((busy_start, busy_end))

    free: list[Interval] = []
    cursor = start
    for busy_start, busy_end in merged:
        if busy_start > cursor:
            free.append(Interval(start=cursor, end=busy_start))
        cursor = busy_end
    if cursor < end:
        free.append(Interval(start=cursor, end=end))
    return free
