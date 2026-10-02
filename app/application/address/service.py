"""Serviço de aplicação da capability de endereço

Orquestra os ports de busca de endereço
"""

from app.domain.address.ports import GeocodingPort, PlacesPort
from app.schemas.address import Address, AddressListResponse, SuggestionsResponse


class AddressService:
    """Orquestra os provedores Google de endereço (`PlacesPort`, `GeocodingPort`)"""

    def __init__(self, places: PlacesPort, geocoding: GeocodingPort) -> None:
        self._places = places
        self._geocoding = geocoding

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

    async def geocode(self, address: str, *, language: str) -> AddressListResponse:
        """Converte um endereço em texto em coordenadas

        Args:
            address: endereço em texto livre
            language: idioma da resposta

        Returns:
            Os endereços encontrados (vazia se nada casar)

        Raises:
            GoogleRateLimitException: quota excedida
            GoogleValidationException: pedido inválido
            GoogleUpstreamException: resposta em formato inesperado
        """
        return AddressListResponse(results=await self._geocoding.geocode(address, language=language))

    async def reverse_geocode(self, latitude: float, longitude: float, *, language: str) -> AddressListResponse:
        """Converte uma coordenada em endereços

        Args:
            latitude: latitude do ponto
            longitude: longitude do ponto
            language: idioma da resposta

        Returns:
            Os endereços encontrados, do mais específico para o menos (vazia se não houver)

        Raises:
            GoogleRateLimitException: quota excedida
            GoogleValidationException: pedido inválido
            GoogleUpstreamException: resposta em formato inesperado
        """
        return AddressListResponse(
            results=await self._geocoding.reverse_geocode(latitude, longitude, language=language)
        )
