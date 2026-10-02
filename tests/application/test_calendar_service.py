"""Testes de app.application.calendar.service.CalendarService"""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.calendar.service import CalendarService, InvalidPeriodError
from app.domain.calendar.ports import OAuthTokens, RefreshTokenRejected
from app.exceptions import (
    CalendarConsentDeniedException,
    CalendarNotConfiguredException,
    CalendarTokenRevokedException,
    GoogleAuthenticationException,
    GoogleNotFoundException,
    GoogleValidationException,
)
from app.infrastructure.calendar.state import CalendarStateSigner
from app.infrastructure.solier.auth.calendar_token_client import (
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    TechnicianTokens,
)
from app.schemas.calendar import Event, EventCreate, EventList, EventUpdate, Interval

START = datetime(2030, 1, 2, 9, 0, tzinfo=UTC)
END = datetime(2030, 1, 2, 18, 0, tzinfo=UTC)


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2030, 1, 2, hour, minute, tzinfo=UTC)


class FakeTokens:
    def __init__(self, tokens: TechnicianTokens | None = None) -> None:
        self.tokens = tokens
        self.saved: list[tuple[str, str, str]] = []
        self.disconnected: list[str] = []
        self.revoked: list[str] = []

    async def get(self, technician_id: str) -> TechnicianTokens | None:
        return self.tokens

    async def save(self, technician_id: str, *, access_token: str, refresh_token: str) -> None:
        self.saved.append((technician_id, access_token, refresh_token))

    async def disconnect(self, technician_id: str) -> None:
        self.disconnected.append(technician_id)

    async def mark_revoked(self, technician_id: str) -> None:
        self.revoked.append(technician_id)


class FakeOAuth:
    def __init__(self) -> None:
        self.refresh_result: str | Exception = "new-at"
        self.exchange_result = OAuthTokens(access_token="at", refresh_token="rt")
        self.revoked: list[str] = []
        self.refreshed: list[str] = []

    def authorization_url(self, state: str) -> str:
        return f"https://accounts.example/auth?state={state}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        self.exchanged = code
        return self.exchange_result

    async def refresh_access_token(self, refresh_token: str) -> str:
        self.refreshed.append(refresh_token)
        if isinstance(self.refresh_result, Exception):
            raise self.refresh_result
        return self.refresh_result

    async def revoke(self, token: str) -> None:
        self.revoked.append(token)


class FakeApi:
    def __init__(self) -> None:
        self.expired_tokens: set[str] = set()
        self.tokens_seen: list[str] = []
        self.busy: list[Interval] = []

    def _use(self, access_token: str) -> None:
        self.tokens_seen.append(access_token)
        if access_token in self.expired_tokens:
            raise GoogleAuthenticationException("expirado", capability="calendar", status_code=401)

    async def free_busy(self, access_token: str, start: datetime, end: datetime) -> list[Interval]:
        self._use(access_token)
        return self.busy

    async def create_event(self, access_token: str, event: EventCreate) -> Event:
        self._use(access_token)
        return Event(event_id="evt1", title=event.title)

    async def list_events(self, access_token: str, start: datetime, end: datetime, page_token: str | None) -> EventList:
        self._use(access_token)
        return EventList(events=[Event(event_id="evt1")], next_page_token=page_token)

    async def update_event(self, access_token: str, event_id: str, update: EventUpdate) -> Event:
        self._use(access_token)
        return Event(event_id=event_id, title=update.title)

    async def delete_event(self, access_token: str, event_id: str) -> None:
        self._use(access_token)


@pytest.fixture
def tokens() -> FakeTokens:
    return FakeTokens(TechnicianTokens(access_token="old-at", refresh_token="rt", status=STATUS_CONNECTED))


@pytest.fixture
def oauth() -> FakeOAuth:
    return FakeOAuth()


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def signer() -> CalendarStateSigner:
    return CalendarStateSigner("segredo-de-teste")


@pytest.fixture
def service(api, oauth, tokens, signer) -> CalendarService:
    return CalendarService(api, oauth, tokens, signer)


def test_connect_returns_a_url_with_a_signed_state_for_the_technician(service, signer):
    url = service.connect("tec-1").authorization_url

    state = url.split("state=")[1]
    assert signer.verify(state) == "tec-1"


def test_connect_requires_oauth_configuration(api, tokens, signer):
    with pytest.raises(CalendarNotConfiguredException):
        CalendarService(api, None, tokens, signer).connect("tec-1")


def test_connect_requires_the_state_secret(api, oauth, tokens):
    with pytest.raises(CalendarNotConfiguredException):
        CalendarService(api, oauth, tokens, None).connect("tec-1")


async def test_complete_connection_exchanges_the_code_and_saves_the_tokens(service, oauth, tokens, signer):
    result = await service.complete_connection("the-code", signer.sign("tec-1"), None)

    assert result.status == "connected"
    assert oauth.exchanged == "the-code"
    assert tokens.saved == [("tec-1", "at", "rt")]


async def test_complete_connection_rejects_a_bad_state_without_saving(service, tokens, signer):
    with pytest.raises(GoogleValidationException) as raised:
        await service.complete_connection("the-code", signer.sign("tec-1") + "x", None)

    assert raised.value.reason == "invalid_state"
    assert tokens.saved == []


async def test_complete_connection_with_consent_denied_saves_nothing(service, oauth, tokens, signer):
    with pytest.raises(CalendarConsentDeniedException) as raised:
        await service.complete_connection(None, signer.sign("tec-1"), "access_denied")

    assert raised.value.technician_id == "tec-1"
    assert tokens.saved == []
    assert not hasattr(oauth, "exchanged")


async def test_complete_connection_with_another_google_error_is_a_validation_error(service, signer):
    with pytest.raises(GoogleValidationException) as raised:
        await service.complete_connection(None, signer.sign("tec-1"), "server_error")

    assert raised.value.reason == "server_error"


@pytest.mark.parametrize("code", [None, ""])
async def test_complete_connection_without_code_or_error_is_a_validation_error(service, signer, code):
    with pytest.raises(GoogleValidationException) as raised:
        await service.complete_connection(code, signer.sign("tec-1"), None)

    assert raised.value.reason == "missing_code"


async def test_complete_connection_requires_configuration(api, tokens):
    with pytest.raises(CalendarNotConfiguredException):
        await CalendarService(api, None, tokens, None).complete_connection("c", "s", None)


async def test_disconnect_revokes_at_google_and_marks_the_connection(service, oauth, tokens):
    await service.disconnect("tec-1")

    assert oauth.revoked == ["rt"]
    assert tokens.disconnected == ["tec-1"]


async def test_disconnect_without_connection_is_a_noop_at_google(service, oauth, tokens):
    tokens.tokens = None

    await service.disconnect("tec-1")

    assert oauth.revoked == []
    assert tokens.disconnected == ["tec-1"]


async def test_disconnect_works_without_oauth_configuration(api, tokens, signer):
    await CalendarService(api, None, tokens, signer).disconnect("tec-1")

    assert tokens.disconnected == ["tec-1"]


async def test_operations_use_the_stored_access_token(service, api):
    event = await service.create_event("tec-1", EventCreate(title="x", start=START, end=END))

    assert event.event_id == "evt1"
    assert api.tokens_seen == ["old-at"]


@pytest.mark.parametrize("stored", [None, TechnicianTokens("a", "r", STATUS_DISCONNECTED)])
async def test_unconnected_technician_is_not_found(service, tokens, api, stored):
    tokens.tokens = stored

    with pytest.raises(GoogleNotFoundException):
        await service.create_event("tec-1", EventCreate(title="x", start=START, end=END))

    assert api.tokens_seen == []


async def test_expired_access_token_is_refreshed_once_and_saved(service, api, oauth, tokens):
    api.expired_tokens.add("old-at")

    event = await service.update_event("tec-1", "evt9", EventUpdate(title="Novo"))

    assert event.event_id == "evt9"
    assert api.tokens_seen == ["old-at", "new-at"]
    assert oauth.refreshed == ["rt"]
    assert tokens.saved == [("tec-1", "new-at", "rt")]


async def test_a_second_401_after_refreshing_is_not_retried_again(service, api):
    api.expired_tokens.update({"old-at", "new-at"})

    with pytest.raises(GoogleAuthenticationException):
        await service.delete_event("tec-1", "evt1")

    assert api.tokens_seen == ["old-at", "new-at"]


async def test_non_401_authentication_errors_do_not_trigger_a_refresh(service, api, oauth, monkeypatch):
    async def forbidden(access_token, event_id):
        raise GoogleAuthenticationException("sem permissão", capability="calendar", status_code=403)

    monkeypatch.setattr(api, "delete_event", forbidden)

    with pytest.raises(GoogleAuthenticationException):
        await service.delete_event("tec-1", "evt1")

    assert oauth.refreshed == []


async def test_rejected_refresh_token_marks_revoked_and_returns_409_error(service, api, oauth, tokens):
    api.expired_tokens.add("old-at")
    oauth.refresh_result = RefreshTokenRejected()

    with pytest.raises(CalendarTokenRevokedException) as raised:
        await service.create_event("tec-1", EventCreate(title="x", start=START, end=END))

    assert raised.value.technician_id == "tec-1"
    assert tokens.revoked == ["tec-1"]
    assert tokens.saved == []


async def test_refresh_requires_oauth_configuration(api, tokens, signer):
    api.expired_tokens.add("old-at")

    with pytest.raises(CalendarNotConfiguredException):
        await CalendarService(api, None, tokens, signer).create_event(
            "tec-1", EventCreate(title="x", start=START, end=END)
        )


async def test_availability_computes_the_free_windows(service, api):
    api.busy = [Interval(start=_at(10), end=_at(12)), Interval(start=_at(14), end=_at(15))]

    result = await service.get_availability("tec-1", START, END)

    assert [(w.start, w.end) for w in result.free] == [(_at(9), _at(10)), (_at(12), _at(14)), (_at(15), _at(18))]
    assert len(result.busy) == 2


async def test_availability_merges_overlapping_and_clamps_to_the_period(service, api):
    api.busy = [
        Interval(start=_at(8), end=_at(10)),
        Interval(start=_at(9, 30), end=_at(11)),
        Interval(start=_at(11), end=_at(12)),
        Interval(start=_at(17), end=_at(20)),
        Interval(start=_at(21), end=_at(22)),
    ]

    result = await service.get_availability("tec-1", START, END)

    assert [(w.start, w.end) for w in result.free] == [(_at(12), _at(17))]


async def test_availability_with_nothing_busy_is_all_free(service):
    result = await service.get_availability("tec-1", START, END)

    assert [(w.start, w.end) for w in result.free] == [(START, END)]


async def test_availability_fully_busy_has_no_free_window(service, api):
    api.busy = [Interval(start=_at(8), end=_at(19))]

    assert (await service.get_availability("tec-1", START, END)).free == []


@pytest.mark.parametrize(
    ("start", "end"),
    [(END, START), (START, START), (START, START + timedelta(days=60, seconds=1))],
)
async def test_invalid_period_is_rejected_before_calling_anything(service, api, start, end):
    with pytest.raises(InvalidPeriodError):
        await service.get_availability("tec-1", start, end)
    with pytest.raises(InvalidPeriodError):
        await service.list_events("tec-1", start, end, None)

    assert api.tokens_seen == []


async def test_period_of_exactly_60_days_is_accepted(service):
    await service.get_availability("tec-1", START, START + timedelta(days=60))


async def test_list_events_passes_the_page_token(service):
    result = await service.list_events("tec-1", START, END, "page-2")

    assert result.next_page_token == "page-2"
