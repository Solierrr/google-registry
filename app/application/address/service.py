"""Serviço de aplicação da capability de endereço

Orquestra os ports de busca de endereço
"""

from app.domain.address.ports import PlacesPort
from app.schemas.address import Address, SuggestionsResponse


class AddressService:
    """Orquestra o provedor Google de endereços (`PlacesPort`)"""

    def __init__(self, places: PlacesPort) -> None:
        self._places = places

    async def suggest(
        self, query: str, *, session_token: str | None, language: str, country: str
    ) -> SuggestionsResponse:
        """Sugere endereços para o texto digitado

        Args:
            query: texto digitado
            session_token: token da sessão de digitação, se houver
            language: idioma das sugestões
            country: país para restringir as sugestões

        Returns:
            As sugestões (vazia se nada casar)

        Raises:
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        suggestions = await self._places.suggest(query, session_token=session_token, language=language, country=country)
        return SuggestionsResponse(suggestions=suggestions)

    async def get_place(self, place_id: str, *, session_token: str | None, language: str) -> Address:
        """Devolve o endereço estruturado de um lugar escolhido nas sugestões

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
        return await self._places.get_details(place_id, session_token=session_token, language=language)
