import re
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_SERVICE_NAME = "google-registry"

_configured = False

_KEY_QUERY_PARAM = re.compile(r"([?&]key=)[^&#]*", re.IGNORECASE)


def redact_api_key(url: str) -> str:
    """Troca o valor do parâmetro de query `key` (chave de API do Google) por `REDACTED`"""
    return _KEY_QUERY_PARAM.sub(r"\1REDACTED", url)


def redact_url_in_span(span: trace.Span, request: Any) -> None:
    """Hook de request do httpx: reescreve a URL registrada no span sem a chave de API

    O instrumentation do httpx grava a URL completa (`url.full`/`http.url`) e só redige
    parâmetros conhecidos, entre os quais não está `key`.
    """
    url = redact_api_key(str(request.url))
    span.set_attribute("url.full", url)
    span.set_attribute("http.url", url)


async def async_redact_url_in_span(span: trace.Span, request: Any) -> None:
    """Versão assíncrona de `redact_url_in_span`, usada pelos `httpx.AsyncClient`"""
    redact_url_in_span(span, request)


def instrument_fastapi(app: FastAPI) -> None:
    """Instrumenta a aplicação FastAPI"""
    FastAPIInstrumentor.instrument_app(app)


def configure_tracing(app: FastAPI) -> None:
    """Configura o `TracerProvider` global, instrumenta o httpx e registra o exporter OTLP"""
    global _configured
    if _configured:
        return
    _configured = True

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: _SERVICE_NAME}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument(request_hook=redact_url_in_span, async_request_hook=async_redact_url_in_span)


def get_tracer() -> trace.Tracer:
    """Retorna um tracer para criação de spans manuais | usado no client Google"""
    return trace.get_tracer(_SERVICE_NAME)
