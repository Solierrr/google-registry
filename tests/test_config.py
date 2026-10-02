"""Configuração carregada do ambiente"""

from app.config import Settings


def test_settings_load_without_the_calendar_oauth_client(monkeypatch):
    for name in (
        "GOOGLE_CALENDAR_OAUTH_CLIENT_ID",
        "GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET",
        "GOOGLE_CALENDAR_OAUTH_REDIRECT_URI",
    ):
        monkeypatch.delenv(name)

    settings = Settings(_env_file=None)

    assert settings.google_calendar_oauth_client_id is None
    assert settings.google_calendar_oauth_client_secret is None
    assert settings.google_calendar_oauth_redirect_uri is None
