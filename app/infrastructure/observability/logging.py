"""Configuração de logging (OpenTelemetry)

destinos: CONSOLE + OTEL

* **console** -> dev(local)
* **OTLP** -> cada log exportado para o OpenTelemetry Collector

Sem Collector rodando o export falha em silêncio e a aplicação continua
"""

import logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

_SERVICE_NAME = "google-registry"
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

_otel_handler: LoggingHandler | None = None


def configure_logging(level: str = "INFO") -> None:
    """Instala o pipeline de logs OTLP + console na raiz

    Chamado uma única vez em `app.main` junto com `configure_tracing`/`configure_metrics`

    Args:
        level: nível mínimo de log em app.config
    """
    global _otel_handler
    if _otel_handler is not None:
        return

    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    provider = LoggerProvider(resource=Resource.create({SERVICE_NAME: _SERVICE_NAME}))
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(provider)

    _otel_handler = LoggingHandler(level=numeric_level, logger_provider=provider)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))
        root.addHandler(console)
    root.addHandler(_otel_handler)


def attach_otel_to_uvicorn() -> None:
    """Anexa o OTEL handler aos loggers do uvicorn (request/access logs -> OTLP)"""
    if _otel_handler is None:
        return
    for name in _UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        if _otel_handler not in logger.handlers:
            logger.addHandler(_otel_handler)
