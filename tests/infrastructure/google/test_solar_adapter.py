"""Testes de app.infrastructure.google.solar.adapter.SolarAdapter"""

import httpx
import pytest
import respx

from app.exceptions import GoogleNotFoundException, GoogleUpstreamException
from app.infrastructure.google.solar.adapter import SolarAdapter
from app.infrastructure.http.google_http_client import GoogleHttpClient

BASE_URL = "https://solar.googleapis.com"
FIND_CLOSEST = f"{BASE_URL}/v1/buildingInsights:findClosest"

SOLAR_POTENTIAL = {
    "maxArrayAreaMeters2": 42.5,
    "maxArrayPanelsCount": 20,
    "maxSunshineHoursPerYear": 1800.0,
    "carbonOffsetFactorKgPerMwh": 400.0,
    "roofSegmentStats": [{"pitchDegrees": 20.0, "azimuthDegrees": 180.0, "stats": {"areaMeters2": 42.5}}],
}
PAYLOAD = {"imageryDate": {"year": 2024, "month": 3, "day": 5}, "solarPotential": SOLAR_POTENTIAL}


@pytest.fixture
async def adapter():
    http_client = GoogleHttpClient(base_url=BASE_URL, capability="solar")
    yield SolarAdapter(http_client, api_key="test-key")
    await http_client.aclose()


@respx.mock
async def test_maps_viability_and_formats_imagery_date(adapter):
    route = respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json=PAYLOAD))

    result = await adapter.get_roof_viability(-23.5, -46.6)

    assert result.imagery_date == "2024-03-05"
    assert result.max_panel_count == 20
    assert result.roof_segments[0].area_m2 == 42.5
    assert route.calls.last.request.headers["X-Goog-Api-Key"] == "test-key"


@respx.mock
async def test_panel_reference_fields_are_empty_when_google_omits_them(adapter):
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json=PAYLOAD))

    result = await adapter.get_roof_viability(-23.5, -46.6)

    assert result.panel_capacity_watts is None
    assert result.panel_width_meters is None
    assert result.panel_height_meters is None
    assert result.panel_configs == []


@respx.mock
async def test_maps_panel_reference_fields(adapter):
    potential = {
        **SOLAR_POTENTIAL,
        "panelCapacityWatts": 400.0,
        "panelWidthMeters": 1.045,
        "panelHeightMeters": 1.879,
        "solarPanelConfigs": [
            {"panelsCount": 4, "yearlyEnergyDcKwh": 1800.0},
            {"panelsCount": 8, "yearlyEnergyDcKwh": 3600.0},
        ],
    }
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json={**PAYLOAD, "solarPotential": potential}))

    result = await adapter.get_roof_viability(-23.5, -46.6)

    assert result.panel_capacity_watts == 400.0
    assert result.panel_width_meters == 1.045
    assert result.panel_height_meters == 1.879
    assert [(c.panels_count, c.yearly_energy_dc_kwh) for c in result.panel_configs] == [(4, 1800.0), (8, 3600.0)]


@respx.mock
async def test_ignores_malformed_panel_configs(adapter):
    potential = {
        **SOLAR_POTENTIAL,
        "solarPanelConfigs": [{"panelsCount": 4, "yearlyEnergyDcKwh": 1800.0}, {"panelsCount": 8}, "invalid"],
    }
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json={**PAYLOAD, "solarPotential": potential}))

    result = await adapter.get_roof_viability(-23.5, -46.6)

    assert [c.panels_count for c in result.panel_configs] == [4]


@respx.mock
async def test_missing_required_field_is_upstream_error(adapter):
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(200, json={**PAYLOAD, "solarPotential": {}}))

    with pytest.raises(GoogleUpstreamException):
        await adapter.get_roof_viability(-23.5, -46.6)


@respx.mock
async def test_not_found_has_friendly_message(adapter):
    respx.get(FIND_CLOSEST).mock(return_value=httpx.Response(404))

    with pytest.raises(GoogleNotFoundException, match="Sem dados para região solicitada"):
        await adapter.get_roof_viability(-23.5, -46.6)
