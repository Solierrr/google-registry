"""Testes de app.infrastructure.llm.probe"""

import asyncio
import contextlib

import httpx
import pytest
import respx

from app.application.llm.key_pool import KeyPool
from app.infrastructure.llm.keys import LlmKey, key_id_for
from app.infrastructure.llm.probe import probe_all, probe_key, run_probes

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GROQ_URL = "https://api.groq.com/openai/v1/models"


def _key(provider: str, secret: str) -> LlmKey:
    return LlmKey(provider=provider, key_id=key_id_for(provider, secret), secret=secret)


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as client:
        yield client


@respx.mock
async def test_gemini_key_is_sent_in_its_header_and_accepted(client):
    route = respx.get(GEMINI_URL).mock(return_value=httpx.Response(200, json={}))

    assert await probe_key(client, _key("gemini", "secret-g")) is True
    request = route.calls.last.request
    assert request.headers["x-goog-api-key"] == "secret-g"
    assert "secret-g" not in str(request.url)


@respx.mock
async def test_groq_key_is_sent_as_bearer_token(client):
    route = respx.get(GROQ_URL).mock(return_value=httpx.Response(200, json={}))

    assert await probe_key(client, _key("groq", "secret-q")) is True
    assert route.calls.last.request.headers["Authorization"] == "Bearer secret-q"


@pytest.mark.parametrize("status", [400, 401, 403])
@respx.mock
async def test_rejected_statuses_mean_invalid_key(client, status):
    respx.get(GEMINI_URL).mock(return_value=httpx.Response(status))

    assert await probe_key(client, _key("gemini", "x")) is False


@pytest.mark.parametrize("status", [429, 500, 503])
@respx.mock
async def test_temporary_errors_do_not_decide_anything(client, status):
    respx.get(GEMINI_URL).mock(return_value=httpx.Response(status))

    assert await probe_key(client, _key("gemini", "x")) is None


@respx.mock
async def test_network_errors_do_not_decide_anything(client):
    respx.get(GEMINI_URL).mock(side_effect=httpx.ConnectError("down"))

    assert await probe_key(client, _key("gemini", "x")) is None


@respx.mock
async def test_probe_all_updates_the_pool_only_when_the_answer_is_known(client):
    good, bad, unknown = _key("gemini", "good"), _key("gemini", "bad"), _key("groq", "unknown")
    pool = KeyPool([good, bad, unknown], clock=lambda: 1000.0)
    respx.get(GEMINI_URL).mock(
        side_effect=lambda request: httpx.Response(200 if request.headers["x-goog-api-key"] == "good" else 400)
    )
    respx.get(GROQ_URL).mock(return_value=httpx.Response(503))

    await probe_all(client, pool)

    statuses = {k.key_id: k.status for p in pool.snapshot().providers for k in p.keys}
    assert statuses == {good.key_id: "available", bad.key_id: "invalid", unknown.key_id: "available"}
    assert [pool.lease().secret for _ in range(2)] == ["good", "unknown"]


@respx.mock
async def test_run_probes_checks_on_start_and_stops_when_cancelled():
    key = _key("gemini", "k")
    pool = KeyPool([key], clock=lambda: 1000.0)
    route = respx.get(GEMINI_URL).mock(return_value=httpx.Response(200, json={}))

    task = asyncio.create_task(run_probes(pool, 3600))
    for _ in range(100):
        if route.called:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.01)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert route.call_count == 1
    assert pool.snapshot().providers[0].keys[0].last_checked_at is not None
