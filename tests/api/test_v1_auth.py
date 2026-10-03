"""Autenticação por token de consumidor em todas as rotas /v1 (exceto /health e o callback do Calendar)"""

import pytest

from app.config import get_settings

CONSUMER_TOKEN = "test-consumer-token"
BODY_ROUTES = {
    "origin": {"latitude": -23.55, "longitude": -46.63},
    "destination": {"latitude": -23.56, "longitude": -46.65},
}
EVENT = {"title": "Visita", "start": "2030-01-02T09:00:00-03:00", "end": "2030-01-02T10:00:00-03:00"}
PERIOD = {"from": "2030-01-02T00:00:00-03:00", "to": "2030-01-03T00:00:00-03:00"}

PROTECTED = [
    ("post", "/v1/address/suggestions", {"json": {"input": "av paulista"}}),
    ("get", "/v1/address/places/abc", {}),
    ("post", "/v1/address/geocode", {"json": {"address": "av paulista 1000"}}),
    ("post", "/v1/address/reverse-geocode", {"json": {"latitude": -23.5, "longitude": -46.6}}),
    ("post", "/v1/address/validate", {"json": {"address": "av paulista 1000"}}),
    ("post", "/v1/address/resolve", {"json": {"query": "av paulista 1000"}}),
    ("get", "/v1/solar/roof-viability", {"params": {"latitude": -23.5, "longitude": -46.6}}),
    ("get", "/v1/geo/timezone", {"params": {"latitude": -23.5, "longitude": -46.6}}),
    ("post", "/v1/i18n/translate", {"json": {"fields": [{"field_name": "a", "text": "oi"}]}}),
    ("post", "/v1/routes/compute", {"json": BODY_ROUTES}),
    ("get", "/v1/weather/hourly", {"params": {"latitude": -23.5, "longitude": -46.6}}),
    ("get", "/v1/calendar/connect", {"params": {"technician_id": "tec-1"}}),
    ("delete", "/v1/calendar/technicians/tec-1/connection", {}),
    ("get", "/v1/calendar/technicians/tec-1/availability", {"params": PERIOD}),
    ("post", "/v1/calendar/technicians/tec-1/events", {"json": EVENT}),
    ("get", "/v1/calendar/technicians/tec-1/events", {"params": PERIOD}),
    ("patch", "/v1/calendar/technicians/tec-1/events/evt1", {"json": {"title": "x"}}),
    ("delete", "/v1/calendar/technicians/tec-1/events/evt1", {}),
    ("get", "/v1/llm/providers", {}),
]


@pytest.fixture(scope="module")
def anon():
    """Um único cliente por módulo: as settings são lidas a cada requisição, então o app não precisa reiniciar"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as shared:
        yield shared


def _ids(cases):
    return [f"{method.upper()} {path}" for method, path, _ in cases]


@pytest.mark.parametrize(("method", "path", "kwargs"), PROTECTED, ids=_ids(PROTECTED))
def test_routes_reject_a_missing_token(anon, method, path, kwargs):
    response = getattr(anon, method)(path, **kwargs)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path", "kwargs"), PROTECTED, ids=_ids(PROTECTED))
def test_routes_reject_a_wrong_token(anon, method, path, kwargs):
    response = getattr(anon, method)(path, headers={"Authorization": "Bearer outro"}, **kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "kwargs"), PROTECTED, ids=_ids(PROTECTED))
def test_routes_fail_closed_when_the_token_is_not_configured(anon, monkeypatch, method, path, kwargs):
    monkeypatch.delenv("REGISTRY_CONSUMER_TOKEN")
    get_settings.cache_clear()

    response = getattr(anon, method)(path, headers={"Authorization": f"Bearer {CONSUMER_TOKEN}"}, **kwargs)

    assert response.status_code == 503


def test_a_user_jwt_is_not_a_substitute_for_the_consumer_token(anon):
    response = anon.get(
        "/v1/geo/timezone",
        params={"latitude": -23.5, "longitude": -46.6},
        headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6ImsxIn0.e30.assinatura"},
    )

    assert response.status_code == 401


def test_the_consumer_token_opens_the_routes(anon):
    response = anon.get(
        "/v1/geo/timezone",
        params={"latitude": -23.55, "longitude": -46.63},
        headers={"Authorization": f"Bearer {CONSUMER_TOKEN}"},
    )

    assert response.status_code == 200


def test_health_stays_open(anon):
    assert anon.get("/health").status_code == 200


def test_calendar_callback_stays_open_because_it_is_protected_by_the_signed_state(anon):
    response = anon.get("/v1/calendar/callback", params={"code": "c", "state": "invalido"})

    assert response.status_code == 400
    assert response.json()["code"] == "GoogleValidationException"
