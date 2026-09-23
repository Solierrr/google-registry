"""DTOs públicos da capability de i18n (`/v1/i18n/...`)

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece
em `app.infrastructure.google.translation.adapter`
"""

from uuid import UUID

from pydantic import BaseModel, Field


class TranslationField(BaseModel):
    """Um campo de texto livre a ser traduzido"""

    field_name: str = Field(..., description="Nome da coluna/campo de origem (ex.: 'information')")
    text: str = Field(..., description="Texto no idioma de origem")


class TranslateRequest(BaseModel):
    """Pedido de tradução de um registro inserido/atualizado em api-core"""

    entity_table: str = Field(..., description="Tabela de origem em api-core (ex.: 'certification')")
    entity_id: UUID = Field(..., description="Id do registro em api-core")
    fields: list[TranslationField] = Field(..., min_length=1, description="Campos de texto a traduzir")
    source_language: str | None = Field(
        default=None, description="Idioma de origem (ISO 639-1). Omitido, é detectado automaticamente"
    )


class TranslatedField(BaseModel):
    """Um campo já traduzido para um dos idiomas suportados"""

    field_name: str = Field(..., description="Nome da coluna/campo de origem")
    language: str = Field(..., description="Idioma de destino (ISO 639-1: en/es/pt)")
    value: str = Field(..., description="Texto traduzido")


class TranslateResponse(BaseModel):
    """Resultado da tradução de um registro"""

    entity_table: str = Field(..., description="Tabela de origem em api-core")
    entity_id: UUID = Field(..., description="Id do registro em api-core")
    source_language: str = Field(..., description="Idioma de origem detectado (ou informado)")
    translations: list[TranslatedField] = Field(..., description="Campos traduzidos pros outros idiomas suportados")
