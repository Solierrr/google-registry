"""Métricas de chamadas às APIs Google

intrumentos de medição|métricas:
`_requests` -> contador de requests divido por variaveis
`_request_duration` -> histograma de tempo de resposta das requests
"""

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

_SERVICE_NAME = "google-registry"

_requests: Counter | None = None
_request_duration: Histogram | None = None
_internal_requests: Counter | None = None
_internal_request_duration: Histogram | None = None


def configure_metrics() -> None:
    """Instala o `MeterProvider` OTLP e cria os instrumentos para métricas"""
    global _requests, _request_duration, _internal_requests, _internal_request_duration
    if _requests is not None:
        return

    provider = MeterProvider(
        resource=Resource.create({SERVICE_NAME: _SERVICE_NAME}),
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(_SERVICE_NAME)

    _requests = meter.create_counter(
        "google.requests",
        unit="{request}",
        description="Total de requests para APIs Google, por capability e resultado",
    )
    _request_duration = meter.create_histogram(
        "google.request.duration",
        unit="s",
        description="Duração das requests par APIs Google, por capability e resultado.",
    )
    _internal_requests = meter.create_counter(
        "solier.internal.requests",
        unit="{request}",
        description="Total de requests para serviços internos Solier (api-persistence/api-auth), por serviço e resultado",
    )
    _internal_request_duration = meter.create_histogram(
        "solier.internal.request.duration",
        unit="s",
        description="Duração das requests para serviços internos Solier, por serviço e resultado.",
    )


def record_google_request(
    *, capability: str, duration_seconds: float, status_code: int | None, error_type: str | None
) -> None:
    """Registra uma chamada Google concluída nas duas métricas

    Args:
        capability: nome da capability que originou a chamada
        duration_seconds: tempo total da chamada, incluindo retries
        status_code: status HTTP da resposta (ausente em timeout/erro de rede)
        error_type: valor de `error.type` se a chamada falhou, ou `None` se teve sucesso
    """
    if _requests is None or _request_duration is None:
        return

    attributes: dict[str, str] = {"google.capability": capability}
    if status_code is not None:
        attributes["http.response.status_code"] = str(status_code)
    if error_type is not None:
        attributes["error.type"] = error_type

    _requests.add(1, attributes)
    _request_duration.record(duration_seconds, attributes)


def record_internal_request(
    *, service: str, duration_seconds: float, status_code: int | None, error_type: str | None
) -> None:
    """Registra uma chamada a um serviço interno Solier concluída nas duas métricas

    Args:
        service: nome do serviço interno chamado
        duration_seconds: tempo total da chamada, incluindo retries
        status_code: status HTTP da resposta (ausente em timeout/erro de rede)
        error_type: valor de `error.type` se a chamada falhou, ou `None` se teve sucesso
    """
    if _internal_requests is None or _internal_request_duration is None:
        return

    attributes: dict[str, str] = {"solier.service": service}
    if status_code is not None:
        attributes["http.response.status_code"] = str(status_code)
    if error_type is not None:
        attributes["error.type"] = error_type

    _internal_requests.add(1, attributes)
    _internal_request_duration.record(duration_seconds, attributes)
