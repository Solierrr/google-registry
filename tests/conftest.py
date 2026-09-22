"""Fixtures compartilhadas dos testes do google-registry."""

import os

_REQUIRED_ENV_DEFAULTS = {
    "GOOGLE_KEY_MAPS": "test-google-key-maps",
    "GOOGLE_KEY_TRANSLATION": "test-google-key-translation",
    "GOOGLE_CALENDAR_OAUTH_CLIENT_ID": "test-client-id",
    "GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_CALENDAR_OAUTH_REDIRECT_URI": "http://localhost/oauth/callback",
    "PERSISTENCE_BASE_URL": "http://localhost:8080",
    "AUTH_BASE_URL": "http://localhost:8081",
}

for _name, _value in _REQUIRED_ENV_DEFAULTS.items():
    os.environ.setdefault(_name, _value)
