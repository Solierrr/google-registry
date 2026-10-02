"""Testes dos cabeçalhos padrão de app.infrastructure.http.internal_http_client.InternalHttpClient"""

import httpx
import respx

from app.infrastructure.http.internal_http_client import InternalHttpClient

URL = "http://auth.test/internal/ping"


@respx.mock
async def test_default_headers_are_sent_on_every_request():
    route = respx.get(URL).mock(return_value=httpx.Response(200))
    client = InternalHttpClient(base_url="http://auth.test", service="auth", headers={"X-Internal-Token": "segredo"})

    await client.request("GET", "/internal/ping")

    assert route.calls.last.request.headers["X-Internal-Token"] == "segredo"
    await client.aclose()


@respx.mock
async def test_no_internal_token_header_when_none_is_configured():
    route = respx.get(URL).mock(return_value=httpx.Response(200))
    client = InternalHttpClient(base_url="http://auth.test", service="auth")

    await client.request("GET", "/internal/ping")

    assert "X-Internal-Token" not in route.calls.last.request.headers
    await client.aclose()
