"""Adapter da Places API (New) do Google (`places:autocomplete` e `places/{id}`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

from typing import Any
from urllib.parse import quote

from app.domain.address.ports import PlacesPort
from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import Address, Suggestion

_AUTOCOMPLETE_PATH = "/v1/places:autocomplete"
_DETAILS_PATH = "/v1/places/"
_DETAILS_FIELD_MASK = "id,formattedAddress,addressComponents,location"
_UNEXPECTED = "Resposta da Places API do Google em formato inesperado"


class PlacesAdapter(PlacesPort):
    """Implementação de `PlacesPort` sobre a Places API (New) do Google"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def suggest(self, query: str, *, session_token: str | None, language: str, country: str) -> list[Suggestion]:
        """Consulta `places:autocomplete` e traduz as previsões para `Suggestion`

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
        body: dict[str, Any] = {"input": query, "languageCode": language, "includedRegionCodes": [country.lower()]}
        if session_token:
            body["sessionToken"] = session_token

        response = await self._http_client.request(
            "POST", _AUTOCOMPLETE_PATH, json=body, headers={"X-Goog-Api-Key": self._api_key}, retry=True
        )
        payload = _json(response)
        raw_suggestions = payload.get("suggestions", [])
        if not isinstance(raw_suggestions, list):
            raise GoogleUpstreamException(_UNEXPECTED, capability="places")
        return [suggestion for raw in raw_suggestions if (suggestion := _to_suggestion(raw)) is not None]

    async def get_details(self, place_id: str, *, session_token: str | None, language: str) -> Address:
        """Consulta `places/{id}` pedindo só os campos de endereço e coordenadas

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
        params: dict[str, str] = {"languageCode": language}
        if session_token:
            params["sessionToken"] = session_token

        try:
            response = await self._http_client.request(
                "GET",
                f"{_DETAILS_PATH}{quote(place_id, safe='')}",
                params=params,
                headers={"X-Goog-Api-Key": self._api_key, "X-Goog-FieldMask": _DETAILS_FIELD_MASK},
            )
        except GoogleNotFoundException as exc:
            raise GoogleNotFoundException(
                "Endereço não encontrado para o place_id informado", capability="places"
            ) from exc

        return _to_address(_json(response))


def _json(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleUpstreamException(_UNEXPECTED, capability="places") from exc
    if not isinstance(payload, dict):
        raise GoogleUpstreamException(_UNEXPECTED, capability="places")
    return payload


def _to_suggestion(raw: Any) -> Suggestion | None:
    """Traduz uma entrada de `suggestions`; ignora previsões de consulta e entradas incompletas"""
    prediction = raw.get("placePrediction") if isinstance(raw, dict) else None
    if not isinstance(prediction, dict):
        return None
    place_id = prediction.get("placeId")
    description = (prediction.get("text") or {}).get("text")
    if not place_id or not description:
        return None
    structured = prediction.get("structuredFormat") or {}
    return Suggestion(
        place_id=place_id,
        description=description,
        main_text=(structured.get("mainText") or {}).get("text"),
        secondary_text=(structured.get("secondaryText") or {}).get("text"),
    )


def _to_address(payload: dict[str, Any]) -> Address:
    try:
        location = payload["location"]
        components = _components_by_type(payload.get("addressComponents") or [])
        return Address(
            place_id=payload.get("id"),
            formatted_address=payload["formattedAddress"],
            street_name=_text(components, "route"),
            street_number=_text(components, "street_number"),
            complement=_text(components, "subpremise"),
            neighborhood=_text(components, "sublocality_level_1") or _text(components, "sublocality"),
            city=_text(components, "locality") or _text(components, "administrative_area_level_2"),
            state=_text(components, "administrative_area_level_1", short=True),
            postal_code=_text(components, "postal_code"),
            country_code=_text(components, "country", short=True),
            latitude=location["latitude"],
            longitude=location["longitude"],
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise GoogleUpstreamException(_UNEXPECTED, capability="places") from exc


def _components_by_type(raw_components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_type: dict[str, dict[str, Any]] = {}
    for component in raw_components:
        for component_type in component.get("types", []):
            by_type.setdefault(component_type, component)
    return by_type


def _text(components: dict[str, dict[str, Any]], component_type: str, *, short: bool = False) -> str | None:
    component = components.get(component_type)
    if component is None:
        return None
    return component.get("shortText" if short else "longText")
