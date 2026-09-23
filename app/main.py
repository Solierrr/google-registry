"""Entrypoint da aplicação FastAPI do google-registry

Monta o `FastAPI`, os clientes HTTP por capability/serviço interno (criados
uma vez no lifespan e reaproveitados por request via `app.api.dependencies`)
e a observabilidade (logging/tracing/metrics OTEL).
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routers import i18n, solar
from app.config import get_settings
from app.exceptions.handlers import register_exception_handlers
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.infrastructure.observability.logging import attach_otel_to_uvicorn, configure_logging
from app.infrastructure.observability.metrics import configure_metrics
from app.infrastructure.observability.tracing import configure_tracing, instrument_fastapi

# Base URL por capability Google - chave usada em app.api.dependencies.get_http_client(capability)
_GOOGLE_BASE_URLS = {
    "solar": "https://solar.googleapis.com",
    "translation": "https://translation.googleapis.com",
}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(app)
    configure_metrics()
    attach_otel_to_uvicorn()

    app.state.google_http_clients = {
        capability: GoogleHttpClient(base_url=base_url, capability=capability)
        for capability, base_url in _GOOGLE_BASE_URLS.items()
    }
    app.state.internal_http_clients = {
        "persistence": InternalHttpClient(base_url=settings.persistence_base_url, service="persistence"),
        "auth": InternalHttpClient(base_url=settings.auth_base_url, service="auth"),
    }

    yield

    for client in app.state.google_http_clients.values():
        await client.aclose()
    for client in app.state.internal_http_clients.values():
        await client.aclose()


app = FastAPI(title="google-registry", lifespan=_lifespan)

instrument_fastapi(app)
register_exception_handlers(app)

app.include_router(solar.router)
app.include_router(i18n.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Healthcheck simples, sem dependências externas"""
    return {"status": "ok"}
