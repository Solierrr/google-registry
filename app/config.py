"""Configuração central do google-registry, carregada de variáveis de ambiente/`.env`
Concentra credenciais Google e parâmetros de infraestrutura
Cada adapter Google recebe suas credenciais por está classe
nenhum outro módulo lê variável de ambiente diretamente
"""

import os
from collections.abc import Mapping
from functools import lru_cache

from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação | instancia unica
    Segredos (`repr=False`) nunca aparecem em logs/repr
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"

    # Maps Platform-> uma api key fornece Places, Geocoding, Address Validation, Routes e Solar
    google_key_maps: str = Field(..., repr=False)

    # Cloud Translation
    google_key_translation: str = Field(..., repr=False)

    # OAuth 2.0 Authorization Code por técnico
    google_calendar_oauth_client_id: str | None = Field(None, repr=False)
    google_calendar_oauth_client_secret: str | None = Field(None, repr=False)
    google_calendar_oauth_redirect_uri: str | None = None
    # Segredo que assina o `state` do fluxo OAuth do Calendar (ausente: as rotas do Calendar respondem 503)
    calendar_state_secret: str | None = Field(None, repr=False)

    # Validação do JWT RS256 de usuário
    jwt_jwks_url: str = "http://localhost:8081/.well-known/jwks.json"
    jwt_issuer: str = "solaria-auth"

    # Token compartilhado dos serviços que consomem /v1/llm/* (ausente: as rotas respondem 503)
    registry_consumer_token: str | None = Field(None, repr=False)

    # repos Solier chamados via HTTP
    auth_base_url: str
    # Enviado ao api-auth em `X-Internal-Token` (`/internal/**`); ausente: o api-auth recusa as chamadas com 401
    internal_api_token: str | None = Field(None, repr=False)

    # Verificação de validade das chaves de LLM em segundo plano (0 desliga)
    llm_probe_interval_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única de `Settings` para o processo atual"""
    return Settings()


def get_llm_environ() -> Mapping[str, str]:
    """Variáveis de ambiente de onde as chaves de LLM são lidas (`<PROVEDOR>_API_KEY_<N>`)

    As variáveis do processo valem mais que as do arquivo `.env`; como o conjunto de chaves é variável,
    elas não são campos de `Settings`
    """
    file_values = {name: value for name, value in dotenv_values(".env").items() if value is not None}
    return {**file_values, **os.environ}
