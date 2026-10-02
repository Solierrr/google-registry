"""Testes dos endpoints /v1/calendar/..."""

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from app.infrastructure.calendar.state import CalendarStateSigner

AUTH_TOKEN_URL = "http://localhost:8081/internal/technicians/tec-1/google-calendar-token"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
OAUTH_REVOKE = "https://oauth2.googleapis.com/revoke"
FREE_BUSY = "https://www.googleapis.com/calendar/v3/freeBusy"
EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

STORED = {"accessToken": "old-at", "refreshToken": "rt", "status": "CONNECTED"}
EVENT = {
    "id": "evt1",
    "summary": "Visita",
    "start": {"dateTime": "2030-01-02T09:00:00-03:00", "timeZone": "America/Sao_Paulo"},
    "end": {"dateTime": "2030-01-02T10:00:00-03:00", "timeZone": "America/Sao_Paulo"},
    "htmlLink": "https://calendar.google.com/event?eid=evt1",
}
EVENT_BODY = {"title": "Visita", "start": "2030-01-02T09:00:00-03:00", "end": "2030-01-02T10:00:00-03:00"}
PERIOD = {"from": "2030-01-02T00:00:00-03:00", "to": "2030-01-03T00:00:00-03:00"}


def _state(technician_id: str = "tec-1") -> str:
    return CalendarStateSigner("test-calendar-state-secret").sign(technician_id)


def test_connect_returns_the_google_consent_url_with_a_signed_state(client):
    response = client.get("/v1/calendar/connect", params={"technician_id": "tec-1"})

    assert response.status_code == 200
    url = urlparse(response.json()["authorization_url"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert query["client_id"] == ["test-calendar-client-id"]
    assert query["access_type"] == ["offline"]
    assert CalendarStateSigner("test-calendar-state-secret").verify(query["state"][0]) == "tec-1"


def test_connect_requires_the_technician_id(client):
    assert client.get("/v1/calendar/connect").status_code == 422


@pytest.mark.parametrize("variable", ["CALENDAR_STATE_SECRET", "GOOGLE_CALENDAR_OAUTH_CLIENT_ID"])
def test_calendar_is_503_when_the_oauth_is_not_configured(monkeypatch, variable):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.delenv(variable)
    with TestClient(app) as unconfigured:
        response = unconfigured.get("/v1/calendar/connect", params={"technician_id": "tec-1"})

    assert response.status_code == 503
    assert response.json()["code"] == "CalendarNotConfiguredException"


@respx.mock
def test_callback_saves_the_tokens_in_api_auth_with_the_internal_token(client):
    respx.post(OAUTH_TOKEN).mock(return_value=httpx.Response(200, json={"access_token": "at", "refresh_token": "rt"}))
    save = respx.put(AUTH_TOKEN_URL).mock(return_value=httpx.Response(204))

    response = client.get("/v1/calendar/callback", params={"code": "the-code", "state": _state()})

    assert response.status_code == 200
    assert response.json() == {"status": "connected"}
    request = save.calls.last.request
    assert json.loads(request.content) == {"accessToken": "at", "refreshToken": "rt"}
    assert request.headers["X-Internal-Token"] == "test-internal-token"


@respx.mock(assert_all_called=False)
@pytest.mark.parametrize("state", ["lixo", "abc.def"])
def test_callback_with_a_bad_state_is_400(client, state):
    response = client.get("/v1/calendar/callback", params={"code": "c", "state": state})

    assert response.status_code == 400
    assert response.json()["code"] == "GoogleValidationException"


@respx.mock(assert_all_called=False)
def test_callback_with_consent_denied_is_409_and_saves_nothing(client):
    save = respx.put(AUTH_TOKEN_URL).mock(return_value=httpx.Response(204))

    response = client.get("/v1/calendar/callback", params={"error": "access_denied", "state": _state()})

    assert response.status_code == 409
    assert response.json()["code"] == "CalendarConsentDeniedException"
    assert response.json()["details"] == {"technician_id": "tec-1"}
    assert not save.called


@respx.mock
def test_callback_with_a_used_code_is_400(client):
    respx.post(OAUTH_TOKEN).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

    response = client.get("/v1/calendar/callback", params={"code": "used", "state": _state()})

    assert response.status_code == 400


@respx.mock
def test_disconnect_revokes_and_marks_the_connection(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    revoke = respx.post(OAUTH_REVOKE).mock(return_value=httpx.Response(200))
    disconnect = respx.delete(AUTH_TOKEN_URL).mock(return_value=httpx.Response(204))

    response = client.delete("/v1/calendar/technicians/tec-1/connection")

    assert response.status_code == 204
    assert b"token=rt" in revoke.calls.last.request.content
    assert disconnect.called


@respx.mock
def test_disconnect_without_connection_is_204(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(404))
    respx.delete(AUTH_TOKEN_URL).mock(return_value=httpx.Response(404))

    assert client.delete("/v1/calendar/technicians/tec-1/connection").status_code == 204


@respx.mock
def test_availability_returns_busy_and_free(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    respx.post(FREE_BUSY).mock(
        return_value=httpx.Response(
            200,
            json={
                "calendars": {"primary": {"busy": [{"start": "2030-01-02T12:00:00Z", "end": "2030-01-02T13:00:00Z"}]}}
            },
        )
    )

    response = client.get("/v1/calendar/technicians/tec-1/availability", params=PERIOD)

    assert response.status_code == 200
    body = response.json()
    assert body["busy"] == [{"start": "2030-01-02T12:00:00Z", "end": "2030-01-02T13:00:00Z"}]
    assert len(body["free"]) == 2


@respx.mock
def test_availability_refreshes_an_expired_access_token(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    respx.post(OAUTH_TOKEN).mock(return_value=httpx.Response(200, json={"access_token": "new-at"}))
    save = respx.put(AUTH_TOKEN_URL).mock(return_value=httpx.Response(204))
    free_busy = respx.post(FREE_BUSY).mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"calendars": {"primary": {"busy": []}}}),
        ]
    )

    response = client.get("/v1/calendar/technicians/tec-1/availability", params=PERIOD)

    assert response.status_code == 200
    assert free_busy.calls.last.request.headers["Authorization"] == "Bearer new-at"
    assert json.loads(save.calls.last.request.content) == {"accessToken": "new-at", "refreshToken": "rt"}


@respx.mock
def test_revoked_grant_is_409_and_marks_the_connection_revoked(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    respx.post(FREE_BUSY).mock(return_value=httpx.Response(401))
    respx.post(OAUTH_TOKEN).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    revoked = respx.patch(f"{AUTH_TOKEN_URL}/revoke").mock(return_value=httpx.Response(204))

    response = client.get("/v1/calendar/technicians/tec-1/availability", params=PERIOD)

    assert response.status_code == 409
    assert response.json()["code"] == "CalendarTokenRevokedException"
    assert response.json()["details"] == {"technician_id": "tec-1"}
    assert revoked.called


@respx.mock
def test_unconnected_technician_is_404(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(404))

    response = client.get("/v1/calendar/technicians/tec-1/availability", params=PERIOD)

    assert response.status_code == 404


@respx.mock(assert_all_called=False)
@pytest.mark.parametrize(
    "params",
    [
        {"from": "2030-01-03T00:00:00-03:00", "to": "2030-01-02T00:00:00-03:00"},
        {"from": "2030-01-01T00:00:00Z", "to": "2030-04-01T00:00:00Z"},
        {"from": "2030-01-02T00:00:00", "to": "2030-01-03T00:00:00"},
        {"from": "2030-01-02T00:00:00Z"},
    ],
)
@pytest.mark.parametrize("path", ["availability", "events"])
def test_invalid_period_is_422_before_any_call(client, params, path):
    google = respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))

    response = client.get(f"/v1/calendar/technicians/tec-1/{path}", params=params)

    assert response.status_code == 422
    assert not google.called


@respx.mock
def test_create_event_is_201(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    create = respx.post(EVENTS).mock(return_value=httpx.Response(200, json=EVENT))

    response = client.post("/v1/calendar/technicians/tec-1/events", json=EVENT_BODY)

    assert response.status_code == 201
    assert response.json()["event_id"] == "evt1"
    assert response.json()["html_link"] == "https://calendar.google.com/event?eid=evt1"
    assert b"attendees" not in create.calls.last.request.content


@pytest.mark.parametrize(
    "body",
    [
        {**EVENT_BODY, "start": "2030-01-02T11:00:00-03:00"},
        {**EVENT_BODY, "start": "2030-01-02T09:00:00"},
        {**EVENT_BODY, "title": ""},
        {"title": "x"},
    ],
)
def test_create_event_validates_the_body(client, body):
    assert client.post("/v1/calendar/technicians/tec-1/events", json=body).status_code == 422


@respx.mock
def test_list_events_returns_the_page(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    route = respx.get(EVENTS).mock(return_value=httpx.Response(200, json={"items": [EVENT], "nextPageToken": "page-2"}))

    response = client.get("/v1/calendar/technicians/tec-1/events", params={**PERIOD, "page_token": "page-1"})

    assert response.status_code == 200
    assert response.json()["events"][0]["event_id"] == "evt1"
    assert response.json()["next_page_token"] == "page-2"
    assert route.calls.last.request.url.params["pageToken"] == "page-1"


@respx.mock
def test_update_event_is_partial(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    patch = respx.patch(f"{EVENTS}/evt1").mock(return_value=httpx.Response(200, json=EVENT))

    response = client.patch("/v1/calendar/technicians/tec-1/events/evt1", json={"title": "Novo"})

    assert response.status_code == 200
    assert json.loads(patch.calls.last.request.content) == {"summary": "Novo"}


@pytest.mark.parametrize("body", [{}, {"time_zone": "America/Sao_Paulo"}, {"title": ""}])
def test_update_event_requires_at_least_one_consistent_field(client, body):
    assert client.patch("/v1/calendar/technicians/tec-1/events/evt1", json=body).status_code == 422


@respx.mock
def test_update_unknown_event_is_404(client):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    respx.patch(f"{EVENTS}/nope").mock(return_value=httpx.Response(404))

    assert client.patch("/v1/calendar/technicians/tec-1/events/nope", json={"title": "x"}).status_code == 404


@respx.mock
@pytest.mark.parametrize("status", [204, 404, 410])
def test_delete_event_is_idempotent(client, status):
    respx.get(AUTH_TOKEN_URL).mock(return_value=httpx.Response(200, json=STORED))
    respx.delete(f"{EVENTS}/evt1").mock(return_value=httpx.Response(status))

    assert client.delete("/v1/calendar/technicians/tec-1/events/evt1").status_code == 204
