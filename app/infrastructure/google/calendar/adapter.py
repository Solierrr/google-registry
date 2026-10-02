"""Adapter da Calendar API do Google (`calendar/v3`, agenda `primary`)

Único lugar que conhece o formato de request/response do Google para eventos e disponibilidade
"""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from app.domain.calendar.ports import CalendarApiPort
from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.calendar import Event, EventCreate, EventList, EventUpdate, Interval

_FREE_BUSY_PATH = "/calendar/v3/freeBusy"
_EVENTS_PATH = "/calendar/v3/calendars/primary/events"
_PAGE_SIZE = 50
_GONE = 410


class CalendarAdapter(CalendarApiPort):
    """Implementação de `CalendarApiPort` sobre a Calendar API do Google"""

    def __init__(self, http_client: GoogleHttpClient) -> None:
        self._http_client = http_client

    async def free_busy(self, access_token: str, start: datetime, end: datetime) -> list[Interval]:
        """Consulta `freeBusy` da agenda principal

        Args:
            access_token: access token do técnico
            start: início do período
            end: fim do período

        Returns:
            Os intervalos ocupados informados pelo Google

        Raises:
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        response = await self._http_client.request(
            "POST",
            _FREE_BUSY_PATH,
            json={"timeMin": start.isoformat(), "timeMax": end.isoformat(), "items": [{"id": "primary"}]},
            headers=_auth(access_token),
            retry=True,
        )
        payload = _json_object(response)
        try:
            calendar = payload["calendars"]["primary"]
            if calendar.get("errors"):
                raise _unexpected_format()
            return [
                Interval(start=_parse_time(item["start"]), end=_parse_time(item["end"])) for item in calendar["busy"]
            ]
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise _unexpected_format() from exc

    async def create_event(self, access_token: str, event: EventCreate) -> Event:
        """Cria o evento na agenda principal, sem convidados e sem e-mail

        Args:
            access_token: access token do técnico
            event: dados do evento

        Returns:
            O evento criado

        Raises:
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
        """
        body: dict[str, Any] = {
            "summary": event.title,
            "start": _time_field(event.start, event.time_zone),
            "end": _time_field(event.end, event.time_zone),
        }
        if event.location is not None:
            body["location"] = event.location
        if event.description is not None:
            body["description"] = event.description
        response = await self._http_client.request(
            "POST", _EVENTS_PATH, json=body, headers=_auth(access_token), retry=False
        )
        return _to_event(_json_object(response))

    async def list_events(self, access_token: str, start: datetime, end: datetime, page_token: str | None) -> EventList:
        """Lista os eventos do período, ordenados por início e com recorrências expandidas

        Args:
            access_token: access token do técnico
            start: início do período
            end: fim do período
            page_token: token da página pedida (`None`: primeira)

        Returns:
            A página de eventos

        Raises:
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
        """
        params: dict[str, Any] = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": _PAGE_SIZE,
        }
        if page_token:
            params["pageToken"] = page_token
        response = await self._http_client.request("GET", _EVENTS_PATH, params=params, headers=_auth(access_token))
        payload = _json_object(response)
        raw_events = payload.get("items", [])
        if not isinstance(raw_events, list):
            raise _unexpected_format()
        events = [event for event in map(_try_event, raw_events) if event is not None]
        next_page_token = payload.get("nextPageToken")
        return EventList(events=events, next_page_token=next_page_token if isinstance(next_page_token, str) else None)

    async def update_event(self, access_token: str, event_id: str, update: EventUpdate) -> Event:
        """Atualiza só os campos enviados

        Args:
            access_token: access token do técnico
            event_id: identificador do evento
            update: campos a alterar

        Returns:
            O evento depois da atualização

        Raises:
            GoogleNotFoundException: evento inexistente
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
        """
        body: dict[str, Any] = {}
        if update.title is not None:
            body["summary"] = update.title
        if update.start is not None:
            body["start"] = _time_field(update.start, update.time_zone)
        if update.end is not None:
            body["end"] = _time_field(update.end, update.time_zone)
        if update.location is not None:
            body["location"] = update.location
        if update.description is not None:
            body["description"] = update.description
        response = await self._http_client.request(
            "PATCH", f"{_EVENTS_PATH}/{quote(event_id, safe='')}", json=body, headers=_auth(access_token)
        )
        return _to_event(_json_object(response))

    async def delete_event(self, access_token: str, event_id: str) -> None:
        """Apaga o evento; evento já apagado ou inexistente (404 ou 410) conta como sucesso

        Args:
            access_token: access token do técnico
            event_id: identificador do evento

        Raises:
            GoogleAuthenticationException: access token expirado (`status_code` 401) ou sem permissão
        """
        try:
            await self._http_client.request(
                "DELETE", f"{_EVENTS_PATH}/{quote(event_id, safe='')}", headers=_auth(access_token)
            )
        except GoogleNotFoundException:
            return
        except GoogleUpstreamException as exc:
            if exc.status_code != _GONE:
                raise


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _time_field(moment: datetime, time_zone: str | None) -> dict[str, str]:
    field = {"dateTime": moment.isoformat()}
    if time_zone:
        field["timeZone"] = time_zone
    return field


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _unexpected_format() -> GoogleUpstreamException:
    return GoogleUpstreamException("Resposta da Calendar API do Google em formato inesperado", capability="calendar")


def _json_object(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise _unexpected_format() from exc
    if not isinstance(payload, dict):
        raise _unexpected_format()
    return payload


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _moment(raw: Any) -> tuple[str | None, str | None]:
    """Instante e fuso de um `start`/`end` do Google (`dateTime` em eventos com hora, `date` em dia inteiro)"""
    if not isinstance(raw, dict):
        return None, None
    return _text(raw.get("dateTime")) or _text(raw.get("date")), _text(raw.get("timeZone"))


def _to_event(raw: dict[str, Any]) -> Event:
    event_id = raw.get("id")
    if not isinstance(event_id, str):
        raise _unexpected_format()
    start, time_zone = _moment(raw.get("start"))
    end, end_time_zone = _moment(raw.get("end"))
    return Event(
        event_id=event_id,
        title=_text(raw.get("summary")),
        start=start,
        end=end,
        time_zone=time_zone or end_time_zone,
        location=_text(raw.get("location")),
        status=_text(raw.get("status")),
        html_link=_text(raw.get("htmlLink")),
    )


def _try_event(raw: Any) -> Event | None:
    if not isinstance(raw, dict):
        return None
    try:
        return _to_event(raw)
    except GoogleUpstreamException:
        return None
