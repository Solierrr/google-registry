"""Configuração compartilhada dos testes (fixtures e variáveis de ambiente).

IMPORTANTE: as variáveis de ambiente são definidas no topo deste módulo,
antes de qualquer import de `app`. Isso garante que os testes rodem em
qualquer ambiente (inclusive no CI, onde não existe arquivo .env) e que
as chaves reais do desenvolvedor nunca sejam usadas nos testes.
"""

import os

os.environ["GOOGLE_KEY_MAPS"] = "test-google-key-maps"
os.environ["GOOGLE_KEY_TRANSLATION"] = "test-google-key-translation"
os.environ["GOOGLE_CALENDAR_OAUTH_CLIENT_ID"] = "test-calendar-client-id"
os.environ["GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET"] = "test-calendar-client-secret"
os.environ["GOOGLE_CALENDAR_OAUTH_REDIRECT_URI"] = "http://localhost:8000/calendar/callback"
os.environ["PERSISTENCE_BASE_URL"] = "http://localhost:8080"
os.environ["AUTH_BASE_URL"] = "http://localhost:8081"

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Limpa o cache do get_settings() antes e depois de cada teste

    get_settings() usa @lru_cache, então sem essa limpeza um teste que
    altera configurações vazaria o estado para os testes seguintes.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    """Cliente HTTP de teste da aplicação FastAPI (roda o lifespan, sem I/O real na criação dos clients)"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
