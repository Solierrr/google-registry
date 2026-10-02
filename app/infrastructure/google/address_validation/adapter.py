"""Adapter da Address Validation API do Google (`v1:validateAddress`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

from typing import Any

from app.domain.address.ports import AddressValidationPort
from app.exceptions import GoogleUpstreamException
from app.infrastructure.google.address_components import address_fields, index_by_type
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.address import Address, ValidateRequest, ValidateResponse, Verdict

_PATH = "/v1:validateAddress"
_UNEXPECTED = "Resposta da Address Validation API do Google em formato inesperado"
_UNVALIDATED_GRANULARITIES = {None, "GRANULARITY_UNSPECIFIED", "OTHER"}


class AddressValidationAdapter(AddressValidationPort):
    """Implementação de `AddressValidationPort` sobre a Address Validation API do Google"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def validate(self, request: ValidateRequest) -> ValidateResponse:
        """Consulta `v1:validateAddress` e traduz o resultado para `ValidateResponse`

        Args:
            request: linhas do endereço, CEP, cidade, UF e país

        Returns:
            O veredito, os componentes faltando ou não confirmados e o endereço normalizado

        Raises:
            GoogleValidationException: pedido inválido
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        address: dict[str, Any] = {"regionCode": request.region_code, "addressLines": request.address_lines}
        if request.postal_code:
            address["postalCode"] = request.postal_code
        if request.locality:
            address["locality"] = request.locality
        if request.administrative_area:
            address["administrativeArea"] = request.administrative_area

        response = await self._http_client.request(
            "POST", _PATH, json={"address": address}, headers={"X-Goog-Api-Key": self._api_key}, retry=True
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleUpstreamException(_UNEXPECTED, capability="address_validation") from exc
        return _to_validate_response(payload)


def _to_validate_response(payload: Any) -> ValidateResponse:
    try:
        result = payload["result"]
        verdict = result["verdict"]
        address = result.get("address") or {}
        missing = list(address.get("missingComponentTypes") or [])
        unconfirmed = list(address.get("unconfirmedComponentTypes") or [])
        return ValidateResponse(
            verdict=_verdict(verdict, has_address=bool(address.get("formattedAddress")), missing=missing),
            missing_components=missing,
            unconfirmed_components=unconfirmed,
            address=_to_address(address, result.get("geocode") or {}),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise GoogleUpstreamException(_UNEXPECTED, capability="address_validation") from exc


def _verdict(verdict: dict[str, Any], *, has_address: bool, missing: list[str]) -> Verdict:
    """Resume os sinais do Google em `ok`, `needs_review` ou `invalid`

    - `invalid`: sem endereço formatado ou sem granularidade de validação
    - `ok`: endereço completo, sem componente não confirmado e sem componente faltando
    - `needs_review`: o endereço existe, mas precisa de revisão
    """
    if not has_address or verdict.get("validationGranularity") in _UNVALIDATED_GRANULARITIES:
        return "invalid"
    if verdict.get("addressComplete") and not verdict.get("hasUnconfirmedComponents") and not missing:
        return "ok"
    return "needs_review"


def _to_address(address: dict[str, Any], geocode: dict[str, Any]) -> Address | None:
    location = geocode.get("location")
    formatted = address.get("formattedAddress")
    if not location or not formatted:
        return None

    components = index_by_type(
        ([component["componentType"]], ((component.get("componentName") or {}).get("text"),) * 2)
        for component in address.get("addressComponents") or []
        if "componentType" in component
    )
    fields = address_fields(components)
    postal = address.get("postalAddress") or {}
    fields["state"] = postal.get("administrativeArea") or fields["state"]
    fields["city"] = postal.get("locality") or fields["city"]
    fields["postal_code"] = postal.get("postalCode") or fields["postal_code"]
    fields["country_code"] = postal.get("regionCode") or fields["country_code"]

    return Address(
        place_id=geocode.get("placeId"),
        formatted_address=formatted,
        latitude=location["latitude"],
        longitude=location["longitude"],
        **fields,
    )
