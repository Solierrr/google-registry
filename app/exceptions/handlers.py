"""Traduz `GoogleProviderException` para response padronizado

Formato de erro padrão: `{"code": str, "message": str, "details"?: object}`
O status HTTP vêm  da própria exception
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import GoogleProviderException, InternalServiceException

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


async def _internal_service_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # handler invocado apenas para InternalServiceException 
    assert isinstance(exc, InternalServiceException)
    status_code = exc.http_status
    if status_code >= 500:
        _log.error(
            "Falha %d em %s %s (serviço interno)", status_code, request.method, request.url.path, exc_info=exc
        )
    else:
        _log.warning(
            "Erro %d em %s %s (serviço interno): %s", status_code, request.method, request.url.path, exc
        )
    body: dict[str, object] = {"code": type(exc).__name__, "message": str(exc)}
    details = exc.details()
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """handler para execções não mapeadas
    """
    _log.error("Falha 500 não tratada em %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": "InternalError", "message": "Erro interno ao processar a requisição"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra os handlers de erro do serviço, do mais específico para o mais genérico"""
    app.add_exception_handler(GoogleProviderException, _google_provider_exception_handler)
    app.add_exception_handler(InternalServiceException, _internal_service_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
