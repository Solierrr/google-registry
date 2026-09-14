"""Dependency FastAPI que valida o JWT RS256 de usuário emitido pelo `api-auth` 
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JOSEError

from app.config import Settings, get_settings
from app.infrastructure.auth.jwks_client import JwksClient, get_jwks_client

_ACCESS_TOKEN_TYPE = "access"

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    jwks_client: Annotated[JwksClient, Depends(get_jwks_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Valida o JWT do header `Authorization: Bearer <token>` e retorna o `sub` (id do usuário)

    Args:
        credentials: credenciais extraídas do header `Authorization` ou `None` se o header estiver ausente
        jwks_client: cliente das chaves públicas RS256 do `api-auth`
        settings: configs da api (issuer do JWT)

    Returns:
        id do user autenticado

    Raises:
        HTTPException: 401 
            motivos:
                token ausente; 
                token malformado; 
                sem `kid`; 
                token expirado; 
                assinatura inválida; 
                `kid`/`iss` desconhecidos; 
                não é um access token; 
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação ausente")

    try:
        header = jwt.get_unverified_header(credentials.credentials)
    except JOSEError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação malformado") from exc

    kid = header.get("kid")
    if kid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação sem identificador de chave (kid)")

    key = await jwks_client.get_key(kid)
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação com chave desconhecida")

    try:
        payload = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
        )
    except JOSEError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de autenticação inválido ou expirado") from exc

    if payload.get("token_type") != _ACCESS_TOKEN_TYPE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token não é um access token válido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sem identificador de usuário (sub)")

    return str(user_id)
