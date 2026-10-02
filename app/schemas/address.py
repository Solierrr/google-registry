"""DTOs públicos da capability de endereço (`/v1/address/...`)

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece nos adapters de
`app.infrastructure.google.places`, `geocoding` e `address_validation`
"""

from typing import Literal

from pydantic import BaseModel, Field

Precision = Literal["rooftop", "interpolated", "center", "approximate"]


class Address(BaseModel):
    """Endereço estruturado, com coordenadas"""

    place_id: str | None = Field(default=None, description="Identificador do lugar no Google, quando existe")
    formatted_address: str = Field(..., description="Endereço completo em uma linha")
    street_name: str | None = Field(default=None, description="Nome da rua")
    street_number: str | None = Field(default=None, description="Número")
    complement: str | None = Field(default=None, description="Complemento (sala, apartamento...)")
    neighborhood: str | None = Field(default=None, description="Bairro")
    city: str | None = Field(default=None, description="Cidade")
    state: str | None = Field(default=None, description="UF")
    postal_code: str | None = Field(default=None, description="CEP")
    country_code: str | None = Field(default=None, description="País (ISO 3166-1 alfa-2)")
    latitude: float = Field(..., description="Latitude")
    longitude: float = Field(..., description="Longitude")
    precision: Precision | None = Field(
        default=None, description="Precisão da coordenada (só quando o Google informa, ex.: geocodificação)"
    )
    partial_match: bool = Field(default=False, description="O Google só casou parte do texto informado")


class SuggestionsRequest(BaseModel):
    """Pedido de sugestões de endereço para um texto parcial"""

    query: str = Field(..., min_length=3, description="Texto digitado pelo usuário (mínimo de 3 caracteres)")
    session_token: str | None = Field(
        default=None, description="Token da sessão de digitação; o mesmo deve ser enviado ao pedir os detalhes"
    )
    language: str = Field(default="pt-BR", description="Idioma das sugestões")
    country: str = Field(default="BR", description="País para restringir as sugestões (ISO 3166-1 alfa-2)")


class Suggestion(BaseModel):
    """Uma sugestão de endereço"""

    place_id: str = Field(..., description="Identificador do lugar, para pedir os detalhes")
    description: str = Field(..., description="Texto completo da sugestão")
    main_text: str | None = Field(default=None, description="Parte principal (ex.: rua e número)")
    secondary_text: str | None = Field(default=None, description="Parte secundária (ex.: cidade e estado)")


class SuggestionsResponse(BaseModel):
    """Sugestões de endereço, da mais relevante para a menos"""

    suggestions: list[Suggestion] = Field(..., description="Sugestões (vazia se nada casar)")


class GeocodeRequest(BaseModel):
    """Pedido de coordenadas para um endereço em texto"""

    address: str = Field(..., min_length=3, description="Endereço em texto livre")
    language: str = Field(default="pt-BR", description="Idioma da resposta")


class ReverseGeocodeRequest(BaseModel):
    """Pedido de endereço para uma coordenada"""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude do ponto")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude do ponto")
    language: str = Field(default="pt-BR", description="Idioma da resposta")


class AddressListResponse(BaseModel):
    """Endereços encontrados, do mais relevante/específico para o menos"""

    results: list[Address] = Field(..., description="Endereços encontrados (vazia se nada casar)")


Verdict = Literal["ok", "needs_review", "invalid"]


class ValidateRequest(BaseModel):
    """Pedido de validação de um endereço digitado à mão"""

    address_lines: list[str] = Field(
        ..., min_length=1, max_length=10, description="Linhas do endereço (rua, número, complemento...)"
    )
    postal_code: str | None = Field(default=None, description="CEP, se conhecido")
    locality: str | None = Field(default=None, description="Cidade, se conhecida")
    administrative_area: str | None = Field(default=None, description="UF, se conhecida")
    region_code: str = Field(default="BR", description="País (ISO 3166-1 alfa-2)")


class AddressValidation(BaseModel):
    """Resultado da validação de um endereço"""

    verdict: Verdict = Field(
        ...,
        description=(
            "ok: endereço completo e confirmado; needs_review: existe, mas há componentes "
            "não confirmados ou faltando; invalid: não foi possível validar"
        ),
    )
    missing_components: list[str] = Field(
        default_factory=list, description="Tipos de componente que faltam (ex.: street_number)"
    )
    unconfirmed_components: list[str] = Field(
        default_factory=list, description="Tipos de componente que o Google não conseguiu confirmar"
    )


class ValidateResponse(AddressValidation):
    """Veredito da validação e a versão normalizada do endereço"""

    address: Address | None = Field(
        default=None, description="Endereço normalizado com coordenadas (nulo se o Google não geocodificou)"
    )
