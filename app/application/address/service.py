import logging

from app.domain.address.ports import AddressValidationPort, GeocodingPort, PlacesPort
from app.exceptions import GoogleNotFoundException, GoogleProviderException
from app.schemas.address import (
    Address,
    AddressListResponse,
    AddressValidation,
    ResolveResponse,
    SuggestionsResponse,
    ValidateRequest,
    ValidateResponse,
)

_log = logging.getLogger("google_registry.address")


class AddressService:
    """Orquestra os provedores Google de endereço (`PlacesPort`, `GeocodingPort`, `AddressValidationPort`)"""

    def __init__(self, places: PlacesPort, geocoding: GeocodingPort, validation: AddressValidationPort) -> None:
        self._places = places
        self._geocoding = geocoding
        self._validation = validation

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

    async def validate(self, request: ValidateRequest) -> ValidateResponse:
        """Valida e normaliza um endereço digitado à mão

        Args:
            request: linhas do endereço, CEP, cidade, UF e país

        Returns:
            O veredito, os componentes faltando ou não confirmados e o endereço normalizado

        Raises:
            GoogleValidationException: pedido inválido
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        return await self._validation.validate(request)

    async def resolve(
        self, *, place_id: str | None, query: str | None, session_token: str | None, language: str
    ) -> ResolveResponse:
        """Resolve o endereço final: busca por `place_id` (ou geocodifica o texto) e valida o resultado

        Args:
            place_id: lugar escolhido nas sugestões (exclusivo com `query`)
            query: endereço em texto livre (exclusivo com `place_id`)
            session_token: mesmo token de sessão usado nas sugestões
            language: idioma da resposta

        Returns:
            O endereço com coordenadas e a validação (nula se o serviço de validação falhar)

        Raises:
            GoogleNotFoundException: lugar ou texto sem resultado
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        if place_id is not None:
            address = await self._places.get_details(place_id, session_token=session_token, language=language)
        else:
            assert query is not None
            results = await self._geocoding.geocode(query, language=language)
            if not results:
                raise GoogleNotFoundException("Endereço não encontrado para o texto informado", capability="geocoding")
            address = results[0]

        return ResolveResponse(address=address, validation=await self._validate_resolved(address))

    async def _validate_resolved(self, address: Address) -> AddressValidation | None:
        """Valida o endereço resolvido; falha do Google vira `None` em vez de derrubar a resolução"""
        request = ValidateRequest(
            address_lines=[address.formatted_address],
            postal_code=address.postal_code,
            locality=address.city,
            administrative_area=address.state,
            region_code=address.country_code or "BR",
        )
        try:
            result = await self._validation.validate(request)
        except GoogleProviderException:
            _log.warning("Validação indisponível ao resolver endereço", exc_info=True)
            return None
        return AddressValidation(
            verdict=result.verdict,
            missing_components=result.missing_components,
            unconfirmed_components=result.unconfirmed_components,
        )
