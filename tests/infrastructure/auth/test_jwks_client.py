"""Testes de app.infrastructure.auth.jwks_client.JwksClient"""

import httpx
import pytest
import respx

from app.infrastructure.auth import jwks_client
from app.infrastructure.auth.jwks_client import JwksClient, JwksUnavailableError, get_jwks_client

JWKS_URL = "http://localhost:8081/.well-known/jwks.json"
KEY_1 = {"kid": "k1", "kty": "RSA", "n": "a", "e": "AQAB"}
KEY_2 = {"kid": "k2", "kty": "RSA", "n": "b", "e": "AQAB"}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(jwks_client.time, "monotonic", clock)
    return clock


@respx.mock
async def test_fetches_the_key_set_and_returns_the_key_by_kid(clock):
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [KEY_1, KEY_2]}))
    client = JwksClient()

    assert await client.get_key("k2") == KEY_2
    assert await client.get_key("k1") == KEY_1
    assert route.call_count == 1


@respx.mock
async def test_unknown_kid_returns_none_without_refetching_inside_the_cooldown(clock):
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [KEY_1]}))
    client = JwksClient()

    assert await client.get_key("k1") == KEY_1
    clock.now += 5
    assert await client.get_key("desconhecida") is None
    assert route.call_count == 1


@respx.mock
async def test_unknown_kid_refreshes_the_key_set_after_the_cooldown(clock):
    route = respx.get(JWKS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"keys": [KEY_1]}),
            httpx.Response(200, json={"keys": [KEY_1, KEY_2]}),
        ]
    )
    client = JwksClient()

    assert await client.get_key("k2") is None
    clock.now += 11
    assert await client.get_key("k2") == KEY_2
    assert route.call_count == 2


@respx.mock
async def test_stale_key_set_is_refreshed(clock):
    route = respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [KEY_1]}))
    client = JwksClient()

    await client.get_key("k1")
    clock.now += 301
    await client.get_key("k1")

    assert route.call_count == 2


@respx.mock
async def test_failed_fetch_without_cached_key_is_unavailable(clock):
    respx.get(JWKS_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(JwksUnavailableError):
        await JwksClient().get_key("k1")


@respx.mock
async def test_connection_error_is_unavailable(clock):
    respx.get(JWKS_URL).mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(JwksUnavailableError):
        await JwksClient().get_key("k1")


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, json=["lista"]),
    ],
)
async def test_malformed_key_set_is_unavailable_when_the_key_is_not_cached(clock, response):
    respx.get(JWKS_URL).mock(return_value=response)

    with pytest.raises(JwksUnavailableError):
        await JwksClient().get_key("k1")


@respx.mock
async def test_key_set_without_usable_keys_means_unknown_key(clock):
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json={"keys": [{"kty": "RSA"}, "x"]}))

    assert await JwksClient().get_key("k1") is None


@respx.mock
async def test_cached_key_survives_a_failed_refresh(clock):
    respx.get(JWKS_URL).mock(side_effect=[httpx.Response(200, json={"keys": [KEY_1]}), httpx.Response(503)])
    client = JwksClient()

    await client.get_key("k1")
    clock.now += 301

    assert await client.get_key("k1") == KEY_1


def test_the_process_shares_a_single_client():
    assert get_jwks_client() is get_jwks_client()
