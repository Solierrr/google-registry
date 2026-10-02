import logging

from app.infrastructure.observability import logging as logging_module


def test_configure_logging_silences_loggers_that_print_request_urls(monkeypatch):
    monkeypatch.setattr(logging_module, "_otel_handler", None)
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    try:
        logging_module.configure_logging("INFO")

        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("httpcore").setLevel(logging.NOTSET)
