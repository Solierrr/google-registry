"""Contratos da capability de endereço esperados do provedor"""

from typing import Protocol

from app.schemas.address import Address, Suggestion, ValidateRequest, ValidateResponse


class PlacesPort(Protocol):
    """Operações de busca de endereço por texto e por identificador esperadas"""

    async def suggest(self, query: str, *, session_token: str | None, language: str, country: str) -> list[Suggestion]:
        """Sugere endereços para um texto parcial

        Args:
            query: texto digitado
            session_token: token da sessão de digitação, se houver
            language: idioma das sugestões
            country: país para restringir as sugestões (ISO 3166-1 alfa-2)

        Returns:
            As sugestões, da mais relevante para a menos (vazia se nada casar)

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...

    async def get_details(self, place_id: str, *, session_token: str | None, language: str) -> Address:
        """Devolve o endereço estruturado de um lugar

        Args:
            place_id: identificador do lugar
            session_token: token da sessão de digitação, se houver
            language: idioma da resposta

        Returns:
            O endereço com coordenadas

        Raises:
            GoogleNotFoundException: place_id inexistente ou expirado
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...


class GeocodingPort(Protocol):
    """Operações de geocodificação esperadas"""

    async def geocode(self, address: str, *, language: str) -> list[Address]:
        """Converte um endereço em texto em coordenadas (restrito ao Brasil)

        Args:
            address: endereço em texto livre
            language: idioma da resposta

        Returns:
            Os endereços encontrados (vazia se nada casar), com precisão e indicação de casamento parcial

        Raises:
            GoogleRateLimitException: quota excedida
            GoogleAuthenticationException: chave negada pelo Google
            GoogleValidationException: pedido inválido
            GoogleUnavailableException: erro temporário do Google
            GoogleUpstreamException: resposta em formato inesperado
        """
        ...

    async def reverse_geocode(self, latitude: float, longitude: float, *, language: str) -> list[Address]:
        """Converte uma coordenada em endereços

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            language: idioma da resposta

        Returns:
            Os endereços encontrados, do mais específico para o menos (vazia se não houver)

        Raises:
            GoogleRateLimitException: quota excedida
            GoogleAuthenticationException: chave negada pelo Google
            GoogleValidationException: pedido inválido
            GoogleUnavailableException: erro temporário do Google
            GoogleUpstreamException: resposta em formato inesperado
        """
        ...


class AddressValidationPort(Protocol):
    """Operações de validação de endereço esperadas"""

    async def validate(self, request: ValidateRequest) -> ValidateResponse:
        """Valida e normaliza um endereço

        Args:
            request: linhas do endereço, CEP, cidade, UF e país

        Returns:
            O veredito, os componentes faltando ou não confirmados e o endereço normalizado

        Raises:
            GoogleValidationException: pedido inválido
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        ...
