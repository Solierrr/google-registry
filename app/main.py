"""Ponto de entrada do google-registry.

Monta a aplicação FastAPI: cria os clientes HTTP (Google e internos Solier) no
lifespan, inclui os routers de capability e registra os exception handlers.

Rodar localmente: `uvicorn app.main:app --reload`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dependencies import registered_capabilities, registered_internal_services
from app.api.routers.solar import router as solar_router
from app.config import get_settings
from app.exceptions.handlers import register_exception_handlers
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.infrastructure.observability.tracing import configure_tracing, instrument_fastapi

# Base URL de cada capability Google exposta hoje pela aplicação.
# Nomes usados como chave em `app.api.dependencies.get_http_client(...)`.
_GOOGLE_BASE_URLS: dict[str, str] = {
    "solar": "https://solar.googleapis.com",
}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cria os clientes HTTP usados pelos routers e os fecha no shutdown.

    Cada `GoogleHttpClient`/`InternalHttpClient` é criado uma única vez por
    processo e injetado nas dependências via `request.app.state`, evitando
    reabrir conexões a cada requisição.
    """
    settings = get_settings()

    google_http_clients: dict[str, GoogleHttpClient] = {
        capability: GoogleHttpClient(base_url=_GOOGLE_BASE_URLS[capability], capability=capability)
        for capability in registered_capabilities()
    }

    internal_base_urls = {
        "persistence": settings.persistence_base_url,
        "auth": settings.auth_base_url,
    }
    internal_http_clients: dict[str, InternalHttpClient] = {
        service: InternalHttpClient(base_url=internal_base_urls[service], service=service)
        for service in registered_internal_services()
        if service in internal_base_urls
    }

    app.state.google_http_clients = google_http_clients
    app.state.internal_http_clients = internal_http_clients

    try:
        yield
    finally:
        for google_client in google_http_clients.values():
            await google_client.aclose()
        for internal_client in internal_http_clients.values():
            await internal_client.aclose()


def create_app() -> FastAPI:
    """Constrói a aplicação FastAPI com routers, handlers e observabilidade."""
    app = FastAPI(title="google-registry", lifespan=_lifespan)

    app.include_router(solar_router)
    register_exception_handlers(app)
    configure_tracing(app)
    instrument_fastapi(app)

    return app


app = create_app()


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Verificação simples de disponibilidade do processo, sem dependências externas."""
    return {"status": "ok"}
