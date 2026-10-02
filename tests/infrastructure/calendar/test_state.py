"""Testes de app.infrastructure.calendar.state.CalendarStateSigner"""

import base64

import pytest

from app.infrastructure.calendar.state import CalendarStateSigner, InvalidStateError


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def signer(clock) -> CalendarStateSigner:
    return CalendarStateSigner("segredo-de-teste", ttl_seconds=600, clock=clock)


def test_roundtrip_returns_the_technician(signer):
    assert signer.verify(signer.sign("tec-42")) == "tec-42"


def test_technician_id_with_dots_survives(signer):
    assert signer.verify(signer.sign("a.b.c")) == "a.b.c"


def test_state_is_url_safe(signer):
    state = signer.sign("tec/42?x=y&z")

    assert all(char.isalnum() or char in "-_." for char in state)
    assert signer.verify(state) == "tec/42?x=y&z"


def test_expired_state_is_rejected(signer, clock):
    state = signer.sign("tec-42")
    clock.now += 601

    with pytest.raises(InvalidStateError, match="expirado"):
        signer.verify(state)


def test_state_is_valid_until_the_deadline(signer, clock):
    state = signer.sign("tec-42")
    clock.now += 600

    assert signer.verify(state) == "tec-42"


def test_tampered_payload_is_rejected(signer):
    payload, _, signature = signer.sign("tec-42").rpartition(".")
    forged = base64.urlsafe_b64encode(b"tec-99.9999999999").decode().rstrip("=")

    assert forged != payload
    with pytest.raises(InvalidStateError):
        signer.verify(f"{forged}.{signature}")


def test_state_signed_with_another_secret_is_rejected(clock):
    other = CalendarStateSigner("outro-segredo", clock=clock)

    with pytest.raises(InvalidStateError):
        other.verify(CalendarStateSigner("segredo-de-teste", clock=clock).sign("tec-42"))


@pytest.mark.parametrize("state", ["", "sem-ponto", ".", "abc.def", "###.###"])
def test_malformed_state_is_rejected(signer, state):
    with pytest.raises(InvalidStateError):
        signer.verify(state)


def test_validly_signed_but_malformed_payload_is_rejected(signer):
    payload = base64.urlsafe_b64encode(b"sem-expiracao").decode().rstrip("=")
    state = f"{payload}.{signer._mac(payload)}"

    with pytest.raises(InvalidStateError):
        signer.verify(state)


def test_validly_signed_payload_without_technician_is_rejected(signer):
    payload = base64.urlsafe_b64encode(b".9999999999").decode().rstrip("=")
    state = f"{payload}.{signer._mac(payload)}"

    with pytest.raises(InvalidStateError):
        signer.verify(state)


def test_default_clock_and_ttl_produce_a_valid_state():
    signer = CalendarStateSigner("segredo-de-teste")

    assert signer.verify(signer.sign("tec-1")) == "tec-1"
