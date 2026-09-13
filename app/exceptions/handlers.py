"""Traduz `GoogleProviderException` para response padronizado

Formato de erro padrão: `{"code": str, "message": str, "details"?: object}`
O status HTTP vêm  da própria exception
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import GoogleProviderException

_log = logging.getLogger("google_registry.exceptions")


async def _google_provider_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # handler invocado apenas para GoogleProviderException
    assert isinstance(exc, GoogleProviderException)
    status_code = exc.http_status
    # Toda exceção tratada gera log correlacionado ao trace:
    # 5xx -> ERROR com stack 
    # 4xx -> WARNING só com a mensagem
    if status_code >= 500:
        _log.error("Falha %d em %s %s", status_code, request.method, request.url.path, exc_info=exc)
    else:
        _log.warning("Erro %d em %s %s: %s", status_code, request.method, request.url.path, exc)
    body: dict[str, object] = {"code": type(exc).__name__, "message": str(exc)}
    details = exc.details()
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra handler das exceptions `GoogleProviderException`"""
    app.add_exception_handler(GoogleProviderException, _google_provider_exception_handler)
