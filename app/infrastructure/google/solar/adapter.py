"""Adapter da Solar API do Google (`buildingInsights:findClosest`)

Único lugar que conhece o formato de request/response do Google para esta capability
"""

from typing import Any

from app.domain.solar.ports import SolarPort
from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.http.google_http_client import GoogleHttpClient
from app.schemas.solar import RoofSegment, SolarViability

_FIND_CLOSEST_PATH = "/v1/buildingInsights:findClosest"


class SolarAdapter(SolarPort):
    """Implementação de `SolarPort` sobre a Solar API do Google (`buildingInsights.findClosest`)"""

    def __init__(self, http_client: GoogleHttpClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key

    async def get_roof_viability(self, latitude: float, longitude: float) -> SolarViability:
        """Consulta `buildingInsights:findClosest` e traduz a resposta para `SolarViability`

        Args:
            latitude: latitude do ponto a consultar
            longitude: longitude do ponto a consultar

        Returns:
            A viabilidade solar do telhado mais próximo encontrado pelo Google

        Raises:
            GoogleNotFoundException: sem edifício mapeado/fora de cobertura para a coordenada
            GoogleUpstreamException: resposta HTTP 200 do Google em formato inesperado
        """
        try:
            response = await self._http_client.request(
                "GET",
                _FIND_CLOSEST_PATH,
                params={
                    "location.latitude": latitude,
                    "location.longitude": longitude,
                    "requiredQuality": "BASE",
                    "experiments": "EXPANDED_COVERAGE",
                },
                headers={"X-Goog-Api-Key": self._api_key},
            )
        except GoogleNotFoundException as exc:
            raise GoogleNotFoundException("Sem dados para região solicitada", capability="solar") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleUpstreamException(
                "Resposta da Solar API do Google em formato inesperado", capability="solar"
            ) from exc
        return self._to_solar_viability(payload)

    @staticmethod
    def _to_solar_viability(payload: dict[str, Any]) -> SolarViability:
        try:
            solar_potential = payload["solarPotential"]
            segments = [
                RoofSegment(
                    pitch_degrees=segment["pitchDegrees"],
                    azimuth_degrees=segment["azimuthDegrees"],
                    area_m2=segment["stats"]["areaMeters2"],
                )
                for segment in solar_potential["roofSegmentStats"]
            ]
            return SolarViability(
                imagery_date=_format_imagery_date(payload["imageryDate"]),
                usable_roof_area_m2=solar_potential["maxArrayAreaMeters2"],
                max_panel_count=solar_potential["maxArrayPanelsCount"],
                annual_sunshine_hours=solar_potential["maxSunshineHoursPerYear"],
                carbon_offset_factor_kg_mwh=solar_potential["carbonOffsetFactorKgPerMwh"],
                roof_segments=segments,
            )
        except (KeyError, TypeError) as exc:
            raise GoogleUpstreamException(
                "Resposta da Solar API do Google em formato inesperado", capability="solar"
            ) from exc


def _format_imagery_date(imagery_date: dict[str, int]) -> str:
    """Formata o `imageryDate` do Google (`{year, month, day}`) como `YYYY-MM-DD`

    Args:
        imagery_date: dicionário com as chaves `year`, `month` e `day`

    Returns:
        A data no formato `YYYY-MM-DD`, com mês e dia preenchidos com zero à esquerda
    """
    return f"{imagery_date['year']:04d}-{imagery_date['month']:02d}-{imagery_date['day']:02d}"
