"""Dependency FastAPI que valida o token compartilhado dos serviços consumidores das chaves de LLM"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_registry_consumer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Valida o header `Authorization: Bearer <REGISTRY_CONSUMER_TOKEN>` com comparação em tempo constante

    Args:
        credentials: credenciais extraídas do header `Authorization` ou `None` se ausentes/fora do esquema Bearer
        settings: configs da api (token esperado)

    Raises:
        HTTPException:
        503 se `REGISTRY_CONSUMER_TOKEN` não estiver configurado (nunca libera a rota sem token)
        401 se o token estiver ausente ou não conferir
    """
    expected = (settings.registry_consumer_token or "").strip()
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Autenticação de consumidores não configurada")

    if credentials is None or not secrets.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token de consumidor ausente ou inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
