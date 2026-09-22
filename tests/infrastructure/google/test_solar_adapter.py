"""Testes de `SolarAdapter._to_solar_viability`, focados no payload traduzido."""

from unittest.mock import AsyncMock

import pytest

from app.exceptions import GoogleUpstreamException
from app.infrastructure.google.solar.adapter import SolarAdapter

_BASE_SOLAR_POTENTIAL: dict = {
    "maxArrayAreaMeters2": 42.5,
    "maxArrayPanelsCount": 20,
    "maxSunshineHoursPerYear": 1800.0,
    "carbonOffsetFactorKgPerMwh": 400.0,
    "roofSegmentStats": [
        {"pitchDegrees": 20.0, "azimuthDegrees": 180.0, "stats": {"areaMeters2": 42.5}},
    ],
}

_BASE_PAYLOAD: dict = {
    "imageryDate": {"year": 2024, "month": 3, "day": 15},
    "solarPotential": _BASE_SOLAR_POTENTIAL,
}


def _make_adapter() -> SolarAdapter:
    return SolarAdapter(AsyncMock(), api_key="fake-key")


def test_to_solar_viability_maps_panel_reference_fields() -> None:
    payload = {
        **_BASE_PAYLOAD,
        "solarPotential": {
            **_BASE_SOLAR_POTENTIAL,
            "panelCapacityWatts": 400.0,
            "panelWidthMeters": 1.045,
            "panelHeightMeters": 1.879,
            "solarPanelConfigs": [
                {"panelsCount": 4, "yearlyEnergyDcKwh": 1800.0},
                {"panelsCount": 8, "yearlyEnergyDcKwh": 3600.0},
            ],
        },
    }

    result = SolarAdapter._to_solar_viability(payload)

    assert result.panel_capacity_watts == 400.0
    assert result.panel_width_meters == 1.045
    assert result.panel_height_meters == 1.879
    assert [c.panels_count for c in result.panel_configs] == [4, 8]
    assert [c.yearly_energy_dc_kwh for c in result.panel_configs] == [1800.0, 3600.0]


def test_to_solar_viability_defaults_panel_fields_when_absent() -> None:
    result = SolarAdapter._to_solar_viability(_BASE_PAYLOAD)

    assert result.panel_capacity_watts is None
    assert result.panel_width_meters is None
    assert result.panel_height_meters is None
    assert result.panel_configs == []


def test_to_solar_viability_ignores_malformed_panel_configs() -> None:
    payload = {
        **_BASE_PAYLOAD,
        "solarPotential": {
            **_BASE_SOLAR_POTENTIAL,
            "solarPanelConfigs": [
                {"panelsCount": 4, "yearlyEnergyDcKwh": 1800.0},
                {"panelsCount": 8},  # falta yearlyEnergyDcKwh -> descartado
                "not-a-dict",  # entrada malformada -> descartada
            ],
        },
    }

    result = SolarAdapter._to_solar_viability(payload)

    assert len(result.panel_configs) == 1
    assert result.panel_configs[0].panels_count == 4


def test_to_solar_viability_raises_upstream_error_on_missing_required_field() -> None:
    payload = {"imageryDate": {"year": 2024, "month": 3, "day": 15}, "solarPotential": {}}

    with pytest.raises(GoogleUpstreamException):
        SolarAdapter._to_solar_viability(payload)
