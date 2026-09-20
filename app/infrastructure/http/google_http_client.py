"""Cliente HTTP compartilhado para chamadas a APIs Google

Concentra:
- timeout
- retry/backoff
- tradução de status HTTP de exceptions
- observalidade(OTLP)

Não é função dos adapters que usam esse client:
- lógica de retry
- tratar `httpx`
- instrumentar chamadas maualmente
"""

import asyncio
import random
import time
from typing import Any

import httpx
from opentelemetry.trace import Status, StatusCode

from app.exceptions import (
    GoogleAuthenticationException,
    GoogleNotFoundException,
    GoogleProviderException,
    GoogleRateLimitException,
    GoogleTimeoutException,
    GoogleUnavailableException,
    GoogleUpstreamException,
    GoogleValidationException,
)
from app.infrastructure.observability.metrics import record_google_request
from app.infrastructure.observability.tracing import get_tracer

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})


class GoogleHttpClient:
    """simplificação de `httpx.AsyncClient` com timeout e retry/backoff para uma API Google

    Uma instância é criada por capability e injetada no adapter
    """

    def __init__(self, *, base_url: str, capability: str, timeout: httpx.Timeout | None = None) -> None:
        self._capability = capability
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
            method: método HTTP (GET/POST/PATCH/DELETE)
            url: path relativo ao `base_url` da capability
            retry: 
                `true` força retry
                `false` desliga o retry para 429/5xx 
                `None` realiza retry para métodos idempotentes
                 Falha de conexão pré-envio sempre tem retry 
            **kwargs: parametros extras 

        Returns:
            A resposta HTTP em caso de sucesso (2xx) ou de erro sem retry (400/401/403/404) 
            a interpretação do response é escopo do adapter

        Raises:
            GoogleTimeoutException: timeout de conexão/leitura esgotado em todas as tentativas
            GoogleRateLimitException: 429 mantido após esgotar as tentativas de retry
            GoogleUnavailableException: 5xx ou falha de rede mantido após esgotar as tentativas
            GoogleAuthenticationException: 401/403 (credencial do projeto GCP)
            GoogleValidationException: 400 (parâmetro obrigatório ausente/malformado)
            GoogleNotFoundException: 404
            GoogleUpstreamException: status HTTP inesperado (ex.: 4xx fora da lista acima)
        """
        retry_on_status = retry if retry is not None else (method.upper() in _IDEMPOTENT_METHODS)
        started_at = time.monotonic()
        status_code: int | None = None
        error_type: str | None = None

        # incia um span para requests
        with self._tracer.start_as_current_span(
            f"google.{self._capability}",
            attributes={"google.capability": self._capability, "http.request.method": method},
        ) as span:
            try:
                response = await self._request_with_retry(
                    method, # GET, POST, PUT, DELETE...
                    url, # URL da API google
                    retry_on_status=retry_on_status, # [GET, PUT, DELETE]
                    **kwargs # headers, params...
                )
                status_code = response.status_code
                span.set_attribute("http.response.status_code", status_code)
                return response
            except GoogleProviderException as exc:
                status_code = exc.status_code
                error_type = exc.error_type
                span.set_attribute("error.type", error_type)
                if status_code is not None:
                    span.set_attribute("http.response.status_code", status_code)
                span.set_status(Status(StatusCode.ERROR, error_type))
                raise
            finally:
                record_google_request(
                    capability=self._capability,
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
                    raise GoogleTimeoutException(
                        f"Timeout ao chamar {self._capability}", capability=self._capability
                    ) from exc
                await self._sleep_backoff(attempt)
                continue
            except httpx.TransportError as exc:
                last_error = exc
                # ConnectError retenta independente
                connect_phase = isinstance(exc, httpx.ConnectError)
                if (not retry_on_status and not connect_phase) or attempt == _MAX_ATTEMPTS:
                    raise GoogleUnavailableException(
                        f"Falha de rede ao chamar {self._capability}", capability=self._capability
                    ) from exc
                await self._sleep_backoff(attempt)
                continue

            retryable = response.status_code in _RETRYABLE_STATUS_CODES and retry_on_status
            if not retryable or attempt == _MAX_ATTEMPTS:
                return self._raise_for_non_retryable(response)

            await self._sleep_backoff(attempt)

        raise GoogleUpstreamException(
            f"Falha ao chamar {self._capability} após {_MAX_ATTEMPTS} tentativas", capability=self._capability
        ) from last_error

    def _raise_for_non_retryable(self, response: httpx.Response) -> httpx.Response:
        status = response.status_code
        if status in (401, 403):
            raise GoogleAuthenticationException(
                f"Falha de autenticação/permissão em {self._capability} (HTTP {status})",
                capability=self._capability,
                status_code=status,
            )
        if status == 400:
            raise GoogleValidationException(
                f"Requisição inválida para {self._capability} (HTTP 400)",
                capability=self._capability,
                status_code=status,
                reason=self._extract_reason(response),
            )
        if status == 404:
            raise GoogleNotFoundException(
                f"Recurso não encontrado em {self._capability} (HTTP 404)",
                capability=self._capability,
                status_code=status,
            )
        if status == 429:
            raise GoogleRateLimitException(
                f"Quota excedida em {self._capability} (HTTP 429)", capability=self._capability, status_code=status
            )
        if status >= 500:
            raise GoogleUnavailableException(
                f"{self._capability} indisponível (HTTP {status})", capability=self._capability, status_code=status
            )
        if status >= 400:
            raise GoogleUpstreamException(
                f"Resposta HTTP inesperada de {self._capability} (HTTP {status})",
                capability=self._capability,
                status_code=status,
            )
        return response

    @staticmethod
    def _extract_reason(response: httpx.Response) -> str | None:
        """Extrai o campo `error` do corpo de um HTTP 400, se houver
        """
        try:
            body = response.json()
        except ValueError:
            return None
        if not isinstance(body, dict):
            return None
        error = body.get("error")
        if isinstance(error, str):
            return error
        if isinstance(error, dict) and isinstance(error.get("status"), str):
            return error["status"]
        return None

    async def _sleep_backoff(self, attempt: int) -> None:
        # calculo de espera para retry
        delay = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        # thread espera tempo de delay + tempo aleatório de até 25%
        await asyncio.sleep(delay + random.uniform(0, delay * 0.25))

    async def aclose(self) -> None:
        """Fecha o pool de conexões"""
        await self._client.aclose()
