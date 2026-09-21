"""Cliente HTTP do endereço/geolocalização de um `place_id`, hospedados em `api-persistence`

Grava (`PUT /internal/geolocalizations/place-id/{placeId}`) o endereço consultado no google é salvo 
no BD (`Address`/`Geolocalization`), serve como um cache para consulta nas APIs google
"""

import logging
from urllib.parse import quote

from app.exceptions import InternalServiceException
from app.infrastructure.http.internal_http_client import InternalHttpClient

_log = logging.getLogger("google_registry.solier.geolocalization_client")

_BASE_PATH = "/internal/geolocalizations/place-id"


class GeolocalizationHttpClient:
    """Grava, via `api-persistence`, o endereço/geolocalização resolvido para um `place_id`"""

    def __init__(self, http_client: InternalHttpClient) -> None:
        self._http_client = http_client

    async def upsert(
        self,
        *,
        place_id: str,
        formatted_address: str,
        latitude: float,
        longitude: float,
        precision: str,
        partial_match: bool,
        street_name: str | None = None,
        street_number: str | None = None,
        complement: str | None = None,
        neighborhood: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
    ) -> None:
        """Grava (ou atualiza) o endereço/geolocalização do `place_id` em `api-persistence`
        """
        try:
            await self._http_client.request(
                "PUT",
                f"{_BASE_PATH}/{quote(place_id, safe='')}",
                json={
                    "formattedAddress": formatted_address,
                    "latitude": latitude,
                    "longitude": longitude,
                    "precision": precision,
                    "partialMatch": partial_match,
                    "streetName": street_name,
                    "streetNumber": street_number,
                    "complement": complement,
                    "neighborhood": neighborhood,
                    "city": city,
                    "state": state,
                    "postalCode": postal_code,
                },
            )
        except InternalServiceException:
            _log.warning("Falha ao gravar place_id %s em api-persistence", place_id)
