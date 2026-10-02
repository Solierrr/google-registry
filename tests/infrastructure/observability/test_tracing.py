"""Testes de app.infrastructure.observability.tracing"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.infrastructure.observability.tracing import async_redact_url_in_span, redact_api_key, redact_url_in_span


def test_redact_api_key_replaces_only_the_key_parameter():
    url = "https://maps.googleapis.com/maps/api/geocode/json?address=rua&key=SECRET&language=pt"

    assert (
        redact_api_key(url) == "https://maps.googleapis.com/maps/api/geocode/json?address=rua&key=REDACTED&language=pt"
    )


def test_redact_api_key_keeps_urls_without_key_and_other_params_with_key_suffix():
    assert redact_api_key("https://x.test/a?monkey=1") == "https://x.test/a?monkey=1"
    assert redact_api_key("https://x.test/a?q=1") == "https://x.test/a?q=1"


def test_redact_api_key_handles_key_as_first_parameter():
    assert redact_api_key("https://x.test/a?key=SECRET&q=1") == "https://x.test/a?key=REDACTED&q=1"


@pytest.fixture
def local_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args):
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = HTTPXClientInstrumentor()
    # outro teste pode já ter instrumentado o httpx (o lifespan da app o faz uma vez por processo)
    instrumentor.uninstrument()
    instrumentor.instrument(
        tracer_provider=provider, request_hook=redact_url_in_span, async_request_hook=async_redact_url_in_span
    )
    yield exporter
    instrumentor.uninstrument()


async def test_traced_httpx_request_does_not_export_the_api_key(exporter, local_server):
    async with httpx.AsyncClient() as client:
        await client.get(f"{local_server}/geocode/json", params={"address": "x", "key": "SECRET"})

    spans = exporter.get_finished_spans()
    assert spans
    exported = " ".join(str(value) for span in spans for value in span.attributes.values())
    assert "SECRET" not in exported
    assert "key=REDACTED" in exported
