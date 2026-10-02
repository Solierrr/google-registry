"""Testes de app.infrastructure.google.calendar.oauth_adapter.CalendarOAuthAdapter"""

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from app.domain.calendar.ports import RefreshTokenRejected
from app.exceptions import GoogleUnavailableException, GoogleUpstreamException, GoogleValidationException
from app.infrastructure.google.calendar.oauth_adapter import CalendarOAuthAdapter, OAuthClientConfig
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://oauth2.googleapis.com"
TOKEN = f"{BASE_URL}/token"
REVOKE = f"{BASE_URL}/revoke"
CONFIG = OAuthClientConfig(
    client_id="client-id", client_secret="client-secret", redirect_uri="http://x/v1/calendar/callback"
)


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="calendar_oauth")
    yield CalendarOAuthAdapter(http_client, CONFIG)
    await http_client.aclose()


def _form(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


def test_authorization_url_asks_for_offline_access_and_explicit_consent():
    adapter = CalendarOAuthAdapter(GoogleHttpClient(base_url=BASE_URL, capability="calendar_oauth"), CONFIG)

    url = urlparse(adapter.authorization_url("state-123"))
    query = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://x/v1/calendar/callback"]
    assert query["response_type"] == ["code"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["state"] == ["state-123"]
    assert query["scope"] == [
        "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.freebusy"
    ]
    assert "client-secret" not in url.query


@respx.mock
async def test_exchange_code_sends_the_authorization_code_grant(adapter):
    route = respx.post(TOKEN).mock(
        return_value=httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "expires_in": 3599})
    )

    tokens = await adapter.exchange_code("the-code")

    assert (tokens.access_token, tokens.refresh_token) == ("at", "rt")
    assert _form(route.calls.last.request) == {
        "code": "the-code",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "redirect_uri": "http://x/v1/calendar/callback",
        "grant_type": "authorization_code",
    }


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [{"access_token": "at"}, {"refresh_token": "rt"}, {"access_token": 1, "refresh_token": 2}, {}],
)
async def test_exchange_code_without_both_tokens_is_upstream_error(adapter, payload):
    respx.post(TOKEN).mock(return_value=httpx.Response(200, json=payload))

    with pytest.raises(GoogleUpstreamException):
        await adapter.exchange_code("the-code")


@respx.mock
@pytest.mark.parametrize("response", [httpx.Response(200, content=b"<html>"), httpx.Response(200, json=["x"])])
async def test_exchange_code_with_unexpected_body_is_upstream_error(adapter, response):
    respx.post(TOKEN).mock(return_value=response)

    with pytest.raises(GoogleUpstreamException):
        await adapter.exchange_code("the-code")


@respx.mock
async def test_exchange_code_with_a_used_code_is_validation_error(adapter):
    respx.post(TOKEN).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

    with pytest.raises(GoogleValidationException):
        await adapter.exchange_code("used")


@respx.mock
async def test_exchange_code_is_not_retried_on_server_error(adapter):
    route = respx.post(TOKEN).mock(return_value=httpx.Response(503))

    with pytest.raises(GoogleUnavailableException):
        await adapter.exchange_code("the-code")

    assert route.call_count == 1


@respx.mock
async def test_refresh_returns_the_new_access_token(adapter):
    route = respx.post(TOKEN).mock(return_value=httpx.Response(200, json={"access_token": "new-at"}))

    assert await adapter.refresh_access_token("rt") == "new-at"
    assert _form(route.calls.last.request) == {
        "refresh_token": "rt",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "grant_type": "refresh_token",
    }


@respx.mock
async def test_refresh_with_invalid_grant_means_the_token_was_rejected(adapter):
    respx.post(TOKEN).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

    with pytest.raises(RefreshTokenRejected):
        await adapter.refresh_access_token("rt")


@respx.mock
async def test_refresh_with_another_bad_request_is_a_validation_error(adapter):
    respx.post(TOKEN).mock(return_value=httpx.Response(400, json={"error": "invalid_client"}))

    with pytest.raises(GoogleValidationException):
        await adapter.refresh_access_token("rt")


@respx.mock
async def test_refresh_is_retried_on_server_error(adapter):
    route = respx.post(TOKEN).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"access_token": "new-at"})]
    )

    assert await adapter.refresh_access_token("rt") == "new-at"
    assert route.call_count == 2


@respx.mock
async def test_refresh_without_access_token_is_upstream_error(adapter):
    respx.post(TOKEN).mock(return_value=httpx.Response(200, json={"expires_in": 3599}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.refresh_access_token("rt")


@respx.mock
async def test_revoke_sends_the_token(adapter):
    route = respx.post(REVOKE).mock(return_value=httpx.Response(200))

    await adapter.revoke("rt")

    assert _form(route.calls.last.request) == {"token": "rt"}


@respx.mock
@pytest.mark.parametrize("response", [httpx.Response(400, json={"error": "invalid_token"}), httpx.Response(503)])
async def test_revoke_failure_is_tolerated(adapter, response):
    respx.post(REVOKE).mock(return_value=response)

    await adapter.revoke("rt")
