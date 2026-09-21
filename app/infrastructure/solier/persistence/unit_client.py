"""Cliente HTTP dos dados ligados a uma `LocalUnit` real, hospedados em `api-persistence`


- vincula o endereço/geolocalização já resolvido de um `place_id` a uma unidade
  (`PUT /internal/local-units/{id}/address-by-place-id/{placeId}`);
- grava o perfil solar da unidade (`local_unit_solar_profile`), via
  `PUT /internal/local-units/{id}/solar-profile`

"""

import logging
from typing import Any
from urllib.parse import quote

from app.exceptions import InternalServiceException
from app.infrastructure.http.internal_http_client import InternalHttpClient
from app.schemas.solar import SolarViability

_log = logging.getLogger("google_registry.solier.unit_client")


def _viability_to_payload(viability: SolarViability) -> dict[str, Any]:
    return {
        "imageryDate": viability.imagery_date,
        "usableRoofAreaM2": viability.usable_roof_area_m2,
        "maxPanelCount": viability.max_panel_count,
        "annualSunshineHours": viability.annual_sunshine_hours,
        "carbonOffsetFactorKgMwh": viability.carbon_offset_factor_kg_mwh,
        "roofSegments": [
            {"pitchDegrees": s.pitch_degrees, "azimuthDegrees": s.azimuth_degrees, "areaM2": s.area_m2}
            for s in viability.roof_segments
        ],
    }


class PersistenceUnitClient:
    """Vincula endereço/perfil solar resolvidos do Google a uma `LocalUnit` real, via `api-persistence`."""

    def __init__(self, http_client: InternalHttpClient) -> None:
        self._http_client = http_client

    async def attach_address_by_place_id(self, unit_id: str, place_id: str) -> None:
        """Vincula a unidade ao endereço/geolocalização já resolvido para `place_id`.

        """
        try:
            await self._http_client.request(
                "PUT",
                f"/internal/local-units/{quote(unit_id, safe='')}"
                f"/address-by-place-id/{quote(place_id, safe='')}",
            )
        except InternalServiceException:
            _log.warning("Falha ao vincular unidade %s ao place_id %s em api-persistence", unit_id, place_id)

    async def upsert_solar_profile(self, unit_id: str, viability: SolarViability) -> None:
        """Grava (ou atualiza) o perfil solar da unidade em `api-persistence`
        """
        try:
            await self._http_client.request(
                "PUT",
                f"/internal/local-units/{quote(unit_id, safe='')}/solar-profile",
                json=_viability_to_payload(viability),
            )
        except InternalServiceException:
            _log.warning("Falha ao gravar perfil solar da unidade %s em api-persistence", unit_id)
