"""Testes de app.infrastructure.google.calendar.adapter.CalendarAdapter"""

import json
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.exceptions import (
    GoogleAuthenticationException,
    GoogleNotFoundException,
    GoogleUpstreamException,
)
from app.infrastructure.google.calendar.adapter import CalendarAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.calendar import EventCreate, EventUpdate

BASE_URL = "https://www.googleapis.com"
FREE_BUSY = f"{BASE_URL}/calendar/v3/freeBusy"
EVENTS = f"{BASE_URL}/calendar/v3/calendars/primary/events"

START = datetime(2030, 1, 2, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
END = datetime(2030, 1, 2, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
GOOGLE_EVENT = {
    "id": "evt1",
    "summary": "Visita",
    "start": {"dateTime": "2030-01-02T09:00:00-03:00", "timeZone": "America/Sao_Paulo"},
    "end": {"dateTime": "2030-01-02T10:00:00-03:00", "timeZone": "America/Sao_Paulo"},
    "location": "Av. Paulista, 1000",
    "status": "confirmed",
    "htmlLink": "https://calendar.google.com/event?eid=evt1",
}


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="calendar")
    yield CalendarAdapter(http_client)
    await http_client.aclose()


@respx.mock
async def test_free_busy_returns_the_busy_intervals(adapter):
    route = respx.post(FREE_BUSY).mock(
        return_value=httpx.Response(
            200,
            json={
                "calendars": {
                    "primary": {
                        "busy": [
                            {"start": "2030-01-02T13:00:00Z", "end": "2030-01-02T14:00:00Z"},
                        ]
                    }
                }
            },
        )
    )

    busy = await adapter.free_busy("at", START, END)

    assert busy[0].start == datetime(2030, 1, 2, 13, 0, tzinfo=UTC)
    assert busy[0].end == datetime(2030, 1, 2, 14, 0, tzinfo=UTC)
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer at"
    assert json.loads(sent.content) == {
        "timeMin": "2030-01-02T09:00:00-03:00",
        "timeMax": "2030-01-02T10:00:00-03:00",
        "items": [{"id": "primary"}],
    }


@respx.mock
async def test_free_busy_is_retried_on_server_error(adapter):
    payload = {"calendars": {"primary": {"busy": []}}}
    route = respx.post(FREE_BUSY).mock(side_effect=[httpx.Response(503), httpx.Response(200, json=payload)])

    assert await adapter.free_busy("at", START, END) == []
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"calendars": {}},
        {"calendars": {"primary": {"errors": [{"reason": "notFound"}], "busy": []}}},
        {"calendars": {"primary": {"busy": [{"start": "x", "end": "y"}]}}},
        {"calendars": {"primary": {"busy": "texto"}}},
        {"calendars": "texto"},
    ],
)
async def test_free_busy_with_unexpected_payload_is_upstream_error(adapter, payload):
    respx.post(FREE_BUSY).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(GoogleUpstreamException):
        await adapter.free_busy("at", START, END)


@respx.mock
@pytest.mark.parametrize("response", [httpx.Response(200, content=b"<html>"), httpx.Response(200, json=["x"])])
async def test_non_object_body_is_upstream_error(adapter, response):
    respx.post(FREE_BUSY).mock(return_value=response)

    with pytest.raises(GoogleUpstreamException):
        await adapter.free_busy("at", START, END)


@respx.mock
async def test_expired_access_token_is_an_authentication_error_with_status_401(adapter):
    respx.post(FREE_BUSY).mock(return_value=httpx.Response(401))

    with pytest.raises(GoogleAuthenticationException) as raised:
        await adapter.free_busy("at", START, END)

    assert raised.value.status_code == 401


@respx.mock
async def test_create_event_sends_summary_times_and_optionals(adapter):
    route = respx.post(EVENTS).mock(return_value=httpx.Response(200, json=GOOGLE_EVENT))

    event = await adapter.create_event(
        "at",
        EventCreate(
            title="Visita",
            start=START,
            end=END,
            time_zone="America/Sao_Paulo",
            location="Av. Paulista, 1000",
            description="Levar escada",
        ),
    )

    assert event.event_id == "evt1"
    assert event.title == "Visita"
    assert event.start == "2030-01-02T09:00:00-03:00"
    assert event.time_zone == "America/Sao_Paulo"
    assert event.html_link == "https://calendar.google.com/event?eid=evt1"
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer at"
    assert json.loads(sent.content) == {
        "summary": "Visita",
        "start": {"dateTime": "2030-01-02T09:00:00-03:00", "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": "2030-01-02T10:00:00-03:00", "timeZone": "America/Sao_Paulo"},
        "location": "Av. Paulista, 1000",
        "description": "Levar escada",
    }


@respx.mock
async def test_create_event_omits_absent_optionals_and_never_invites(adapter):
    route = respx.post(EVENTS).mock(return_value=httpx.Response(200, json=GOOGLE_EVENT))

    await adapter.create_event("at", EventCreate(title="Visita", start=START, end=END))

    body = json.loads(route.calls.last.request.content)
    assert set(body) == {"summary", "start", "end"}
    assert "timeZone" not in body["start"]
    assert "attendees" not in body


@respx.mock
async def test_create_event_is_not_retried_on_server_error(adapter):
    route = respx.post(EVENTS).mock(return_value=httpx.Response(503))

    with pytest.raises(Exception):  # noqa: B017
        await adapter.create_event("at", EventCreate(title="Visita", start=START, end=END))

    assert route.call_count == 1


@respx.mock
async def test_create_event_without_id_is_upstream_error(adapter):
    respx.post(EVENTS).mock(return_value=httpx.Response(200, json={"summary": "x"}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.create_event("at", EventCreate(title="Visita", start=START, end=END))


@respx.mock
async def test_list_events_orders_expands_and_pages(adapter):
    all_day = {"id": "evt2", "summary": "Folga", "start": {"date": "2030-01-03"}, "end": {"date": "2030-01-04"}}
    route = respx.get(EVENTS).mock(
        return_value=httpx.Response(
            200, json={"items": [GOOGLE_EVENT, all_day, {"summary": "sem id"}, "lixo"], "nextPageToken": "page-2"}
        )
    )

    result = await adapter.list_events("at", START, END, "page-1")

    assert [event.event_id for event in result.events] == ["evt1", "evt2"]
    assert result.events[1].start == "2030-01-03"
    assert result.events[1].time_zone is None
    assert result.next_page_token == "page-2"
    params = route.calls.last.request.url.params
    assert params["singleEvents"] == "true"
    assert params["orderBy"] == "startTime"
    assert params["pageToken"] == "page-1"
    assert params["timeMin"] == "2030-01-02T09:00:00-03:00"


@respx.mock
async def test_list_events_without_page_token_and_last_page(adapter):
    route = respx.get(EVENTS).mock(return_value=httpx.Response(200, json={}))

    result = await adapter.list_events("at", START, END, None)

    assert result.events == []
    assert result.next_page_token is None
    assert "pageToken" not in route.calls.last.request.url.params


@respx.mock
async def test_list_events_with_unexpected_items_is_upstream_error(adapter):
    respx.get(EVENTS).mock(return_value=httpx.Response(200, json={"items": "texto"}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.list_events("at", START, END, None)


@respx.mock
async def test_update_event_sends_only_the_given_fields(adapter):
    route = respx.patch(f"{EVENTS}/evt1").mock(return_value=httpx.Response(200, json=GOOGLE_EVENT))

    event = await adapter.update_event("at", "evt1", EventUpdate(title="Novo", location="Sala 2"))

    assert event.event_id == "evt1"
    assert json.loads(route.calls.last.request.content) == {"summary": "Novo", "location": "Sala 2"}


@respx.mock
async def test_update_event_applies_the_time_zone_to_the_given_times(adapter):
    route = respx.patch(f"{EVENTS}/evt1").mock(return_value=httpx.Response(200, json=GOOGLE_EVENT))

    await adapter.update_event(
        "at", "evt1", EventUpdate(start=START, end=END, time_zone="America/Sao_Paulo", description="d")
    )

    body = json.loads(route.calls.last.request.content)
    assert body["start"] == {"dateTime": "2030-01-02T09:00:00-03:00", "timeZone": "America/Sao_Paulo"}
    assert body["end"] == {"dateTime": "2030-01-02T10:00:00-03:00", "timeZone": "America/Sao_Paulo"}
    assert body["description"] == "d"


@respx.mock
async def test_update_unknown_event_is_not_found(adapter):
    respx.patch(f"{EVENTS}/nope").mock(return_value=httpx.Response(404))

    with pytest.raises(GoogleNotFoundException):
        await adapter.update_event("at", "nope", EventUpdate(title="x"))


@respx.mock
async def test_event_id_is_url_encoded(adapter):
    route = respx.patch(url__regex=r".*/events/a%2Fb%3Fc$").mock(return_value=httpx.Response(200, json=GOOGLE_EVENT))

    await adapter.update_event("at", "a/b?c", EventUpdate(title="x"))

    assert route.called


@respx.mock
async def test_delete_event_succeeds(adapter):
    route = respx.delete(f"{EVENTS}/evt1").mock(return_value=httpx.Response(204))

    await adapter.delete_event("at", "evt1")

    assert route.calls.last.request.headers["Authorization"] == "Bearer at"


@respx.mock
@pytest.mark.parametrize("status", [404, 410])
async def test_delete_is_idempotent_for_missing_or_already_deleted_events(adapter, status):
    respx.delete(f"{EVENTS}/evt1").mock(return_value=httpx.Response(status))

    await adapter.delete_event("at", "evt1")


@respx.mock
async def test_delete_with_expired_token_is_still_an_authentication_error(adapter):
    respx.delete(f"{EVENTS}/evt1").mock(return_value=httpx.Response(401))

    with pytest.raises(GoogleAuthenticationException):
        await adapter.delete_event("at", "evt1")


@respx.mock
async def test_delete_with_other_unexpected_status_is_upstream_error(adapter):
    respx.delete(f"{EVENTS}/evt1").mock(return_value=httpx.Response(409))

    with pytest.raises(GoogleUpstreamException):
        await adapter.delete_event("at", "evt1")
