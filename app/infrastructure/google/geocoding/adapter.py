from typing import Any

from app.domain.address.ports import GeocodingPort
from app.exceptions import (
    GoogleAuthenticationException,
    GoogleRateLimitException,
    GoogleUnavailableException,
    GoogleUpstreamException,
    GoogleValidationException,
)
from app.infrastructure.google.address_components import address_fields, index_by_type
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import Address

_PATH = "/maps/api/geocode/json"
_UNEXPECTED = "Resposta da Geocoding API do Google em formato inesperado"
_PRECISIONS = {
    "ROOFTOP": "rooftop",
    "RANGE_INTERPOLATED": "interpolated",
    "GEOMETRIC_CENTER": "center",
    "APPROXIMATE": "approximate",
}


class GeocodingAdapter(GeocodingPort):
    """Implementação de `GeocodingPort` sobre a Geocoding API do Google"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def geocode(self, address: str, *, language: str) -> list[Address]:
        """Consulta a Geocoding API por endereço, restrita ao Brasil

        Args:
            address: endereço em texto livre
            language: idioma da resposta

        Returns:
            Os endereços encontrados (vazia se nada casar)

        Raises:
            GoogleRateLimitException: quota excedida
            GoogleAuthenticationException: chave negada pelo Google
            GoogleValidationException: pedido inválido
            GoogleUnavailableException: erro temporário do Google
            GoogleUpstreamException: resposta em formato inesperado
        """
        return await self._call({"address": address, "components": "country:BR", "language": language})

    async def reverse_geocode(self, latitude: float, longitude: float, *, language: str) -> list[Address]:
        """Consulta a Geocoding API por coordenada

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
        return await self._call({"latlng": f"{latitude},{longitude}", "language": language})

    async def _call(self, params: dict[str, str]) -> list[Address]:
        response = await self._http_client.request("GET", _PATH, params={**params, "key": self._api_key})
        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleUpstreamException(_UNEXPECTED, capability="geocoding") from exc
        if not isinstance(payload, dict):
            raise GoogleUpstreamException(_UNEXPECTED, capability="geocoding")

        status = payload.get("status")
        if status == "ZERO_RESULTS":
            return []
        if status != "OK":
            raise _error_for(status, payload.get("error_message"))

        try:
            return [_to_address(raw) for raw in payload["results"]]
        except (KeyError, TypeError, AttributeError) as exc:
            raise GoogleUpstreamException(_UNEXPECTED, capability="geocoding") from exc


def _error_for(status: Any, error_message: Any) -> Exception:
    """Traduz o `status` de erro da Geocoding API para a exceção de domínio correspondente"""
    if status in ("OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT"):
        return GoogleRateLimitException("Quota excedida em geocoding", capability="geocoding")
    if status == "REQUEST_DENIED":
        return GoogleAuthenticationException("Falha de autenticação/permissão em geocoding", capability="geocoding")
    if status == "INVALID_REQUEST":
        reason = error_message if isinstance(error_message, str) else None
        return GoogleValidationException("Requisição inválida para geocoding", capability="geocoding", reason=reason)
    if status == "UNKNOWN_ERROR":
        return GoogleUnavailableException("geocoding indisponível", capability="geocoding")
    return GoogleUpstreamException(_UNEXPECTED, capability="geocoding")


def _to_address(raw: dict[str, Any]) -> Address:
    geometry = raw["geometry"]
    components = index_by_type(
        (component.get("types", []), (component.get("long_name"), component.get("short_name")))
        for component in raw.get("address_components") or []
    )
    return Address(
        place_id=raw.get("place_id"),
        formatted_address=raw["formatted_address"],
        latitude=geometry["location"]["lat"],
        longitude=geometry["location"]["lng"],
        precision=_PRECISIONS.get(geometry.get("location_type")),
        partial_match=bool(raw.get("partial_match", False)),
        **address_fields(components),
    )
