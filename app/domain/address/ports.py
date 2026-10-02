"""Contratos da capability de endereço esperados do provedor"""

from typing import Protocol

from app.schemas.address import Address, Suggestion


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
