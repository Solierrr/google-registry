from pydantic import BaseModel, Field


class RoofSegment(BaseModel):
    """Um segmento (plano) do telhado, com sua inclinação, orientação e área aproveitável."""

    pitch_degrees: float = Field(..., description="Inclinação do segmento em graus, em relação ao plano horizontal")
    azimuth_degrees: float = Field(..., description="Orientação (azimute) do segmento em graus, 0 = norte")
    area_m2: float = Field(..., description="Área aproveitável do segmento, em metros quadrados")


class SolarPanelConfig(BaseModel):
    """Uma configuração candidata de arranjo de painéis, com a produção anual estimada para ela

    A quantidade de painéis é de painéis de referência do Google (`panel_capacity_watts`);
    quem usa outro painel precisa converter a energia pela potência.
    """

    panels_count: int = Field(..., description="Quantidade de painéis de referência nesta configuração")
    yearly_energy_dc_kwh: float = Field(
        ..., description="Energia DC anual estimada para esta configuração, em kWh, antes de perdas do sistema"
    )


class SolarViability(BaseModel):
    """Viabilidade solar do telhado mais próximo da coordenada consultada"""

    imagery_date: str = Field(..., description="Data da imageria usada na análise, no formato YYYY-MM-DD")
    usable_roof_area_m2: float = Field(
        ..., description="Área total do telhado utilizável para painéis, em metros quadrados"
    )
    max_panel_count: int = Field(..., description="Quantidade máxima de painéis solares que cabem no telhado")
    annual_sunshine_hours: float = Field(
        ..., description="Máximo de horas de sol direto por ano estimadas para o telhado"
    )
    carbon_offset_factor_kg_mwh: float = Field(
        ..., description="Fator de compensação de carbono, em kg de CO2 por MWh gerado"
    )
    roof_segments: list[RoofSegment] = Field(
        ..., description="Planos identificados no telhado, cada um com sua inclinação, orientação e área"
    )
    panel_capacity_watts: float | None = Field(
        default=None, description="Potência do painel de referência do Google, em watts (nulo se o Google não informa)"
    )
    panel_width_meters: float | None = Field(
        default=None, description="Largura do painel de referência, em metros (nulo se o Google não informa)"
    )
    panel_height_meters: float | None = Field(
        default=None, description="Altura do painel de referência, em metros (nulo se o Google não informa)"
    )
    panel_configs: list[SolarPanelConfig] = Field(
        default_factory=list,
        description="Configurações candidatas de painéis e energia anual, na ordem do Google (vazia se não houver)",
    )
