"""Configuração de tracing (OpenTelemetry)

Em ambiente dev, sem collector, o export falha silenciosamente e a aplicação continua
"""

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


def instrument_fastapi(app: FastAPI) -> None:
    """Instrumenta a aplicação FastAPI
    """
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

    HTTPXClientInstrumentor().instrument()


def get_tracer() -> trace.Tracer:
    """Retorna um tracer para criação de spans manuais | usado no client Google"""
    return trace.get_tracer(_SERVICE_NAME)
