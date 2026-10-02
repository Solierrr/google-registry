"""Testes de app.infrastructure.google.translation.adapter.TranslationAdapter"""

import json

import httpx
import pytest
import respx

from app.exceptions import GoogleRateLimitException, GoogleUpstreamException
from app.infrastructure.google.translation.adapter import TranslationAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://translation.googleapis.com"


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="translation")
    yield TranslationAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_detect_language_returns_most_likely_language(adapter):
    route = respx.post(f"{BASE_URL}/language/translate/v2/detect").mock(
        return_value=httpx.Response(200, json={"data": {"detections": [[{"language": "pt", "confidence": 1}]]}})
    )

    assert await adapter.detect_language("Olá") == "pt"
    assert route.calls.last.request.headers["X-Goog-Api-Key"] == "test-key"


@respx.mock
async def test_translate_batch_sends_all_texts_and_keeps_order(adapter):
    route = respx.post(f"{BASE_URL}/language/translate/v2").mock(
        return_value=httpx.Response(
            200, json={"data": {"translations": [{"translatedText": "Hello"}, {"translatedText": "Bye"}]}}
        )
    )

    result = await adapter.translate_batch(["Olá", "Tchau"], "en", source_language="pt")

    assert result == ["Hello", "Bye"]
    body = json.loads(route.calls.last.request.read())
    assert body["q"] == ["Olá", "Tchau"]
    assert body["source"] == "pt"
    assert body["target"] == "en"


@respx.mock
async def test_translate_batch_rejects_response_with_different_length(adapter):
    respx.post(f"{BASE_URL}/language/translate/v2").mock(
        return_value=httpx.Response(200, json={"data": {"translations": [{"translatedText": "Hello"}]}})
    )

    with pytest.raises(GoogleUpstreamException):
        await adapter.translate_batch(["Olá", "Tchau"], "en")


@respx.mock
async def test_translate_batch_rejects_malformed_payload(adapter):
    respx.post(f"{BASE_URL}/language/translate/v2").mock(return_value=httpx.Response(200, json={"data": {}}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.translate_batch(["Olá"], "en")


@respx.mock
async def test_translate_batch_retries_rate_limit_then_succeeds(adapter, monkeypatch):
    async def no_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.infrastructure.http.google_http_client.asyncio.sleep", no_sleep)
    route = respx.post(f"{BASE_URL}/language/translate/v2").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"data": {"translations": [{"translatedText": "Hello"}]}}),
        ]
    )

    assert await adapter.translate_batch(["Olá"], "en") == ["Hello"]
    assert route.call_count == 2


@respx.mock
async def test_translate_batch_raises_rate_limit_after_all_attempts(adapter, monkeypatch):
    async def no_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.infrastructure.http.google_http_client.asyncio.sleep", no_sleep)
    respx.post(f"{BASE_URL}/language/translate/v2").mock(return_value=httpx.Response(429))

    with pytest.raises(GoogleRateLimitException):
        await adapter.translate_batch(["Olá"], "en")
