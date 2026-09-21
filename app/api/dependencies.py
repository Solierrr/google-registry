"""Dependências FastAPI compartilhadas

Expõe clientes HTTP criados no lifespan:
- um `GoogleHttpClient` por capability
- um `InternalHttpClient` por serviço interno Solier
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.infrastructure.solier.auth.calendar_token_client import AuthCalendarTokenClient
from app.infrastructure.solier.persistence.geolocalization_client import GeolocalizationHttpClient
from app.infrastructure.solier.persistence.unit_client import PersistenceUnitClient

# Uma dependência memorizada por capability
_http_client_deps: dict[str, Callable[[Request], GoogleHttpClient]] = {}


def get_http_client(capability: str) -> Callable[[Request], GoogleHttpClient]:
    """Fábrica de dependência: resolve o `GoogleHttpClient` da capability, criado no lifespan

    Args:
        capability: chave usada em `app.main._GOOGLE_BASE_URLS` (ex.: "geocoding", "calendar").

    Returns:
        Uma dependência FastAPI (a mesma instância a cada chamada com a mesma `capability`)
    """
    if capability not in _http_client_deps:

        def _resolve(request: Request, _capability: str = capability) -> GoogleHttpClient:
            return request.app.state.google_http_clients[_capability]

        _http_client_deps[capability] = _resolve
    return _http_client_deps[capability]


def registered_capabilities() -> set[str]:
    """Capabilities que algum router já pediu via `get_http_client(...)`"""
    return set(_http_client_deps)


# Uma dependência memorizada por serviço interno Solier (persistence/auth)
_internal_http_client_deps: dict[str, Callable[[Request], InternalHttpClient]] = {}


def get_internal_http_client(service: str) -> Callable[[Request], InternalHttpClient]:
    """Fábrica de dependência: resolve o `InternalHttpClient` do serviço, criado no lifespan

    Args:
        service: chave usada em `app.main` ("persistence" ou "auth").

    Returns:
        Uma dependência FastAPI (a mesma instância a cada chamada com o mesmo `service`)
    """
    if service not in _internal_http_client_deps:

        def _resolve(request: Request, _service: str = service) -> InternalHttpClient:
            return request.app.state.internal_http_clients[_service]

        _internal_http_client_deps[service] = _resolve
    return _internal_http_client_deps[service]


def registered_internal_services() -> set[str]:
    """Serviços internos que algum router já pediu via `get_internal_http_client(...)`"""
    return set(_internal_http_client_deps)


def get_calendar_token_client(
    http_client: Annotated[InternalHttpClient, Depends(get_internal_http_client("auth"))],
) -> AuthCalendarTokenClient:
    """Cliente dos tokens OAuth do Calendar por técnico, ligado ao `InternalHttpClient` do api-auth"""
    return AuthCalendarTokenClient(http_client)


def get_geolocalization_client(
    http_client: Annotated[InternalHttpClient, Depends(get_internal_http_client("persistence"))],
) -> GeolocalizationHttpClient:
    """Cliente do endereço/geolocalização real de um `place_id`, ligado ao `InternalHttpClient` do api-persistence"""
    return GeolocalizationHttpClient(http_client)


def get_persistence_unit_client(
    http_client: Annotated[InternalHttpClient, Depends(get_internal_http_client("persistence"))],
) -> PersistenceUnitClient:
    """Cliente do endereço/perfil solar por unidade, ligado ao `InternalHttpClient` do api-persistence"""
    return PersistenceUnitClient(http_client)
