"""Configuração central do google-registry, carregada de variáveis de ambiente/`.env`
Concentra credenciais Google e parâmetros de infraestrutura
Cada adapter Google recebe suas credenciais por está classe
nenhum outro módulo lê variável de ambiente diretamente
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação | instancia unica
    Segredos (`repr=False`) nunca aparecem em logs/repr
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    # Postgres — usado só para o cache de responses Google
    database_url: str = Field(..., repr=False)

    # Maps Platform: uma chave cobre Places, Geocoding, Address Validation, Routes e Solar
    google_key_maps: str = Field(..., repr=False)

    # Cloud Translation
    google_key_translation: str = Field(..., repr=False)

    # OAuth 2.0 Authorization Code por técnico
    google_calendar_oauth_client_id: str = Field(..., repr=False)
    google_calendar_oauth_client_secret: str = Field(..., repr=False)
    google_calendar_oauth_redirect_uri: str

    # Chave de criptografia dos tokens do Calendar armazenados em `calendar_technician_tokens`
    calendar_token_encryption_key: str = Field(..., repr=False)

    # Validação do JWT RS256 de usuário 
    jwt_jwks_url: str = "http://localhost:8081/.well-known/jwks.json"
    jwt_issuer: str = "solaria-auth"


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única de `Settings` para o processo atual"""
    return Settings()
