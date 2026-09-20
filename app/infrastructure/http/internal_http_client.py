"""Cliente HTTP compartilhado para chamadas aos serviços internos Solier 

Concentra:
- timeout
- retry/backoff
- tradução de status HTTP de exceptions
- observalidade(OTLP)

Estrutura idêntica a `GoogleHttpClient`

`/internal/**`
"""

import asyncio
import random
import time
from typing import Any

import httpx
from opentelemetry.trace import Status, StatusCode

from app.exceptions import (
    InternalServiceException,
    InternalServiceNotFoundException,
    InternalServiceTimeoutException,
    InternalServiceUnavailableException,
    InternalServiceUpstreamException,
    InternalServiceValidationException,
)
from app.infrastructure.observability.metrics import record_internal_request
from app.infrastructure.observability.tracing import get_tracer

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})


class InternalHttpClient:
    """simplificação de `httpx.AsyncClient` com timeout e retry/backoff para um serviço interno Solier

    Uma instância é criada por serviço (persistence|auth)
    """

    def __init__(self, *, base_url: str, service: str, timeout: httpx.Timeout | None = None) -> None:
        self._service = service
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout or httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0),
        )
        self._tracer = get_tracer()

    async def request(
        self, method: str, url: str, *, retry: bool | None = None, **kwargs: Any
    ) -> httpx.Response:
        """Executa a requisição com retry/backoff, span e métricas

        Args:
            method: método HTTP (GET/PUT/PATCH/DELETE)
            url: path relativo ao `base_url` do serviço
            retry:
                `true` força retry
                `false` desliga o retry para 429/5xx
                `None` realiza retry para métodos idempotentes
                 Falha de conexão pré-envio sempre tem retry
            **kwargs: parametros extras

        Returns:
            A resposta HTTP em caso de sucesso (2xx) ou de erro sem retry (400/404)
            a interpretação do response é escopo do client fino da capability

        Raises:
            InternalServiceTimeoutException: timeout de conexão/leitura esgotado em todas as tentativas
            InternalServiceUnavailableException: 5xx ou falha de rede mantido após esgotar as tentativas
            InternalServiceValidationException: 400 (parâmetro obrigatório ausente/malformado)
            InternalServiceNotFoundException: 404
            InternalServiceUpstreamException: status HTTP inesperado (ex.: 401/403/429)
        """
        retry_on_status = retry if retry is not None else (method.upper() in _IDEMPOTENT_METHODS)
        started_at = time.monotonic()
        status_code: int | None = None
        error_type: str | None = None

        with self._tracer.start_as_current_span(
            f"solier.{self._service}",
            attributes={"solier.service": self._service, "http.request.method": method},
        ) as span:
            try:
                response = await self._request_with_retry(
                    method,
                    url,
                    retry_on_status=retry_on_status,
                    **kwargs,
                )
                status_code = response.status_code
                span.set_attribute("http.response.status_code", status_code)
                return response
            except InternalServiceException as exc:
                status_code = exc.status_code
                error_type = exc.error_type
                span.set_attribute("error.type", error_type)
                if status_code is not None:
                    span.set_attribute("http.response.status_code", status_code)
                span.set_status(Status(StatusCode.ERROR, error_type))
                raise
            finally:
                record_internal_request(
                    service=self._service,
                    duration_seconds=time.monotonic() - started_at,
                    status_code=status_code,
                    error_type=error_type,
                )

    async def _request_with_retry(
        self, method: str, url: str, *, retry_on_status: bool, **kwargs: Any
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                last_error = exc
                # ConnectTimeout retenta independente
                connect_phase = isinstance(exc, httpx.ConnectTimeout)
                if (not retry_on_status and not connect_phase) or attempt == _MAX_ATTEMPTS:
                    raise InternalServiceTimeoutException(
                        f"Timeout ao chamar {self._service}", service=self._service
                    ) from exc
                await self._sleep_backoff(attempt)
                continue
            except httpx.TransportError as exc:
                last_error = exc
                # ConnectError retenta independente
                connect_phase = isinstance(exc, httpx.ConnectError)
                if (not retry_on_status and not connect_phase) or attempt == _MAX_ATTEMPTS:
                    raise InternalServiceUnavailableException(
                        f"Falha de rede ao chamar {self._service}", service=self._service
                    ) from exc
                await self._sleep_backoff(attempt)
                continue

            retryable = response.status_code in _RETRYABLE_STATUS_CODES and retry_on_status
            if not retryable or attempt == _MAX_ATTEMPTS:
                return self._raise_for_non_retryable(response)

            await self._sleep_backoff(attempt)

        raise InternalServiceUnavailableException(
            f"Falha ao chamar {self._service} após {_MAX_ATTEMPTS} tentativas", service=self._service
        ) from last_error

    def _raise_for_non_retryable(self, response: httpx.Response) -> httpx.Response:
        status = response.status_code
        if status == 400:
            raise InternalServiceValidationException(
                f"Requisição inválida para {self._service} (HTTP 400)",
                service=self._service,
                status_code=status,
            )
        if status == 404:
            raise InternalServiceNotFoundException(
                f"Recurso não encontrado em {self._service} (HTTP 404)",
                service=self._service,
                status_code=status,
            )
        if status >= 500:
            raise InternalServiceUnavailableException(
                f"{self._service} indisponível (HTTP {status})", service=self._service, status_code=status
            )
        if status >= 300:
            raise InternalServiceUpstreamException(
                f"Resposta HTTP inesperada de {self._service} (HTTP {status})",
                service=self._service,
                status_code=status,
            )
        return response

    async def _sleep_backoff(self, attempt: int) -> None:
        # calculo de espera para retry
        delay = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        # thread espera tempo de delay + tempo aleatório de até 25%
        await asyncio.sleep(delay + random.uniform(0, delay * 0.25))

    async def aclose(self) -> None:
        """Fecha o pool de conexões"""
        await self._client.aclose()
