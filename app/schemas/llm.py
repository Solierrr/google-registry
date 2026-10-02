from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["ok", "rate_limited", "invalid"]
KeyStatus = Literal["available", "cooling_down", "invalid"]


class AuthHeader(BaseModel):
    """Cabeçalho HTTP que autentica a chamada ao provedor"""

    name: str = Field(..., description="Nome do cabeçalho (ex.: x-goog-api-key, Authorization)")
    value: str = Field(..., description="Valor completo do cabeçalho, já com o prefixo exigido pelo provedor")


class KeyLease(BaseModel):
    """Chave entregue para uma chamada ao provedor"""

    provider: str = Field(..., description="Provedor da chave (gemini, groq)")
    key_id: str = Field(..., description="Identificador opaco da chave, para avisar o resultado do uso")
    api_key: str = Field(..., description="Chave de API")
    base_url: str = Field(..., description="URL base da API do provedor")
    auth_header: AuthHeader = Field(..., description="Cabeçalho pronto para autenticar a chamada")


class ReportRequest(BaseModel):
    """Resultado do uso de uma chave"""

    outcome: Outcome = Field(
        ..., description="ok: funcionou; rate_limited: limite de uso atingido; invalid: chave recusada pelo provedor"
    )
    retry_after_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
        description="Em rate_limited, quanto esperar antes de reutilizar a chave (omitido: padrão do registry)",
    )


class KeyState(BaseModel):
    """Estado de uma chave, sem o segredo"""

    key_id: str = Field(..., description="Identificador opaco da chave")
    status: KeyStatus = Field(..., description="available, cooling_down (descansando) ou invalid")
    available_at: datetime | None = Field(default=None, description="Quando volta a ser usada (só em cooling_down)")
    last_checked_at: datetime | None = Field(default=None, description="Última verificação de validade bem-sucedida")


class ProviderState(BaseModel):
    """Chaves de um provedor"""

    provider: str = Field(..., description="Provedor (gemini, groq)")
    keys: list[KeyState] = Field(..., description="Chaves do provedor")


class ProvidersResponse(BaseModel):
    """Estado de todas as chaves configuradas"""

    providers: list[ProviderState] = Field(..., description="Provedores com chaves configuradas")
