"""Endpoints de Calendar (`/v1/calendar/...`)"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import AwareDatetime

from app.api.dependencies import get_calendar_token_client, get_http_client
from app.application.calendar.service import CalendarService, InvalidPeriodError
from app.config import get_settings
from app.infrastructure.auth.consumer_token import require_registry_consumer
from app.infrastructure.calendar.state import CalendarStateSigner
from app.infrastructure.google.calendar.adapter import CalendarAdapter
from app.infrastructure.google.calendar.oauth_adapter import CalendarOAuthAdapter, OAuthClientConfig
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.solier.auth.calendar_token_client import AuthCalendarTokenClient
from app.schemas.calendar import (
    Availability,
    ConnectionStatus,
    ConnectResponse,
    Event,
    EventCreate,
    EventList,
    EventUpdate,
)

router = APIRouter(prefix="/v1/calendar", tags=["calendar"], dependencies=[Depends(require_registry_consumer)])
# O callback é aberto pelo navegador do técnico, que não envia Bearer: a proteção dele é o `state` assinado
public_router = APIRouter(prefix="/v1/calendar", tags=["calendar"])

TechnicianId = Annotated[str, Path(min_length=1, description="Identificador do técnico")]
PeriodStart = Annotated[AwareDatetime, Query(alias="from", description="Início do período (ISO 8601 com fuso)")]
PeriodEnd = Annotated[AwareDatetime, Query(alias="to", description="Fim do período (ISO 8601 com fuso)")]


def _get_service(
    api_client: Annotated[GoogleHttpClient, Depends(get_http_client("calendar"))],
    oauth_client: Annotated[GoogleHttpClient, Depends(get_http_client("calendar_oauth"))],
    tokens: Annotated[AuthCalendarTokenClient, Depends(get_calendar_token_client)],
) -> CalendarService:
    """Monta o `CalendarService`; sem as variáveis do OAuth o consentimento e a renovação respondem 503"""
    settings = get_settings()
    oauth = None
    if (
        settings.google_calendar_oauth_client_id
        and settings.google_calendar_oauth_client_secret
        and settings.google_calendar_oauth_redirect_uri
    ):
        oauth = CalendarOAuthAdapter(
            oauth_client,
            OAuthClientConfig(
                client_id=settings.google_calendar_oauth_client_id,
                client_secret=settings.google_calendar_oauth_client_secret,
                redirect_uri=settings.google_calendar_oauth_redirect_uri,
            ),
        )
    signer = CalendarStateSigner(settings.calendar_state_secret) if settings.calendar_state_secret else None
    return CalendarService(CalendarAdapter(api_client), oauth, tokens, signer)


Service = Annotated[CalendarService, Depends(_get_service)]


@router.get("/connect", summary="Endereço para o técnico conectar a conta Google")
async def connect(technician_id: Annotated[str, Query(min_length=1)], service: Service) -> ConnectResponse:
    """Devolve a URL da tela de consentimento do Google (acesso offline e consentimento explícito).

    Args:
        technician_id: técnico que vai conectar a conta Google
        service: service com os clients injetados

    Returns:
        A URL de consentimento; o `state` embutido é assinado e vale poucos minutos

    Raises:
        CalendarNotConfiguredException: OAuth do Calendar não configurado / HTTP 503
    """
    return service.connect(technician_id)


@public_router.get("/callback", summary="Retorno do consentimento do Google")
async def callback(
    state: Annotated[str, Query(description="`state` devolvido pelo Google")],
    service: Service,
    code: Annotated[str | None, Query(description="Código de autorização do Google")] = None,
    error: Annotated[str | None, Query(description="Erro informado pelo Google no lugar do código")] = None,
) -> ConnectionStatus:
    """Conclui o consentimento: troca o código por tokens e os grava no `api-auth`.

    Args:
        state: `state` devolvido pelo Google
        service: service com os clients injetados
        code: código de autorização do Google
        error: erro informado pelo Google no lugar do código

    Returns:
        `{"status": "connected"}`

    Raises:
        GoogleValidationException: `state` inválido ou expirado / HTTP 400
        CalendarConsentDeniedException: o técnico recusou o consentimento / HTTP 409
    """
    return await service.complete_connection(code, state, error)


@router.delete(
    "/technicians/{technician_id}/connection",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desconecta a conta Google do técnico",
)
async def disconnect(technician_id: TechnicianId, service: Service) -> Response:
    """Revoga o acesso no Google (falha tolerada) e marca a conexão como desconectada. Idempotente.

    Args:
        technician_id: técnico a desconectar
        service: service com os clients injetados
    """
    await service.disconnect(technician_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/technicians/{technician_id}/availability", summary="Disponibilidade do técnico")
async def get_availability(
    technician_id: TechnicianId, start: PeriodStart, end: PeriodEnd, service: Service
) -> Availability:
    """Intervalos ocupados e janelas livres da agenda principal do técnico no período.

    Args:
        technician_id: técnico consultado
        start: início do período
        end: fim do período (no máximo 60 dias depois do início)
        service: service com os clients injetados

    Returns:
        Intervalos ocupados e janelas livres

    Raises:
        HTTPException: 422 se `from >= to` ou o período passar de 60 dias
        GoogleNotFoundException: técnico não conectado / HTTP 404
        CalendarTokenRevokedException: o técnico revogou o acesso / HTTP 409
    """
    try:
        return await service.get_availability(technician_id, start, end)
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/technicians/{technician_id}/events", status_code=status.HTTP_201_CREATED, summary="Cria um evento")
async def create_event(technician_id: TechnicianId, event: EventCreate, service: Service) -> Event:
    """Cria um evento na agenda principal do técnico, sem convidados e sem e-mail.

    Args:
        technician_id: técnico dono da agenda
        event: dados do evento
        service: service com os clients injetados

    Returns:
        O evento criado

    Raises:
        GoogleNotFoundException: técnico não conectado / HTTP 404
        CalendarTokenRevokedException: o técnico revogou o acesso / HTTP 409
    """
    return await service.create_event(technician_id, event)


@router.get("/technicians/{technician_id}/events", summary="Lista os eventos do técnico")
async def list_events(
    technician_id: TechnicianId,
    start: PeriodStart,
    end: PeriodEnd,
    service: Service,
    page_token: Annotated[str | None, Query(description="Token da próxima página")] = None,
) -> EventList:
    """Lista os eventos do período, ordenados por início e com recorrências expandidas.

    Args:
        technician_id: técnico dono da agenda
        start: início do período
        end: fim do período (no máximo 60 dias depois do início)
        service: service com os clients injetados
        page_token: token da próxima página

    Returns:
        A página de eventos

    Raises:
        HTTPException: 422 se `from >= to` ou o período passar de 60 dias
        GoogleNotFoundException: técnico não conectado / HTTP 404
        CalendarTokenRevokedException: o técnico revogou o acesso / HTTP 409
    """
    try:
        return await service.list_events(technician_id, start, end, page_token)
    except InvalidPeriodError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.patch("/technicians/{technician_id}/events/{event_id}", summary="Atualiza um evento")
async def update_event(
    technician_id: TechnicianId,
    event_id: Annotated[str, Path(min_length=1, description="Identificador do evento")],
    update: EventUpdate,
    service: Service,
) -> Event:
    """Atualiza só os campos enviados; ao menos um é obrigatório.

    Args:
        technician_id: técnico dono da agenda
        event_id: identificador do evento
        update: campos a alterar
        service: service com os clients injetados

    Returns:
        O evento depois da atualização

    Raises:
        GoogleNotFoundException: técnico não conectado ou evento inexistente / HTTP 404
        CalendarTokenRevokedException: o técnico revogou o acesso / HTTP 409
    """
    return await service.update_event(technician_id, event_id, update)


@router.delete(
    "/technicians/{technician_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apaga um evento",
)
async def delete_event(
    technician_id: TechnicianId,
    event_id: Annotated[str, Path(min_length=1, description="Identificador do evento")],
    service: Service,
) -> Response:
    """Apaga o evento. Idempotente: evento já inexistente também responde 204.

    Args:
        technician_id: técnico dono da agenda
        event_id: identificador do evento
        service: service com os clients injetados

    Raises:
        GoogleNotFoundException: técnico não conectado / HTTP 404
        CalendarTokenRevokedException: o técnico revogou o acesso / HTTP 409
    """
    await service.delete_event(technician_id, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
