"""Autenticação do consumidor em /v1/llm/..."""

import pytest

from app.config import get_settings

CONSUMER_TOKEN = "test-consumer-token"


@pytest.fixture
def keys_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY_1", "groq-secret-1")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/v1/llm/keys"),
        ("post", "/v1/llm/keys/groq-abc/report"),
        ("get", "/v1/llm/providers"),
    ],
)
def test_llm_routes_reject_a_missing_token(keys_env, anonymous_client, method, path):
    response = getattr(anonymous_client, method)(path)

    assert response.status_code == 401
    assert "groq-secret-1" not in response.text


@pytest.mark.parametrize("header", ["Bearer wrong-token", "Basic dGVzdDp0ZXN0", "Bearer", CONSUMER_TOKEN])
def test_llm_routes_reject_an_invalid_token(keys_env, client, header):
    response = client.get("/v1/llm/keys", headers={"Authorization": header})

    assert response.status_code == 401
    assert "groq-secret-1" not in response.text


def test_llm_routes_accept_the_consumer_token(keys_env, client):
    response = client.get("/v1/llm/keys", headers=_bearer(CONSUMER_TOKEN))

    assert response.status_code == 200
    assert response.json()["api_key"] == "groq-secret-1"


def test_unauthorized_response_asks_for_bearer(keys_env, anonymous_client):
    response = anonymous_client.get("/v1/llm/keys")

    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_llm_routes_fail_closed_when_the_token_is_not_configured(keys_env, client, monkeypatch):
    monkeypatch.delenv("REGISTRY_CONSUMER_TOKEN")
    get_settings.cache_clear()

    response = client.get("/v1/llm/keys", headers=_bearer(CONSUMER_TOKEN))

    assert response.status_code == 503
    assert "groq-secret-1" not in response.text


def test_llm_routes_fail_closed_when_the_token_is_blank(keys_env, client, monkeypatch):
    monkeypatch.setenv("REGISTRY_CONSUMER_TOKEN", "   ")
    get_settings.cache_clear()

    response = client.get("/v1/llm/keys", headers=_bearer("   "))

    assert response.status_code == 503
