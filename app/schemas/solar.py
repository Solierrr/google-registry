"""DTOs públicos da capability de Solar (`/v1/solar/...`).

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece 
em `app.infrastructure.google.solar.adapter`
"""

from pydantic import BaseModel, Field


class RoofSegment(BaseModel):
    """Um segmento (plano) do telhado, com sua inclinação, orientação e área aproveitável."""

    pitch_degrees: float = Field(..., description="Inclinação do segmento em graus, em relação ao plano horizontal")
    azimuth_degrees: float = Field(..., description="Orientação (azimute) do segmento em graus, 0 = norte")
    area_m2: float = Field(..., description="Área aproveitável do segmento, em metros quadrados")


class SolarViability(BaseModel):
    """Viabilidade solar do telhado mais próximo da coordenada consultada
    """

    imagery_date: str = Field(..., description="Data da imageria usada na análise, no formato YYYY-MM-DD")
    usable_roof_area_m2: float = Field(..., description="Área total do telhado utilizável para painéis, em metros quadrados")
    max_panel_count: int = Field(..., description="Quantidade máxima de painéis solares que cabem no telhado")
    annual_sunshine_hours: float = Field(..., description="Máximo de horas de sol direto por ano estimadas para o telhado")
    carbon_offset_factor_kg_mwh: float = Field(
        ..., description="Fator de compensação de carbono, em kg de CO2 por MWh gerado"
    )
    roof_segments: list[RoofSegment] = Field(
        ..., description="Planos identificados no telhado, cada um com sua inclinação, orientação e área"
    )
