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


class SolarPanelConfig(BaseModel):
    """Uma configuração candidata de arranjo de painéis, com sua produção anual estimada.

    Cada configuração representa uma quantidade fixa de painéis do painel de
    referência do Google (`panel_capacity_watts`/`panel_width_meters`/
    `panel_height_meters`) e a energia DC anual estimada para essa quantidade.
    Consumidores que usam um painel de referência diferente devem converter a
    energia proporcionalmente à potência antes de aplicar seu próprio fator
    de desempenho do sistema.
    """

    panels_count: int = Field(..., description="Quantidade de painéis de referência nesta configuração")
    yearly_energy_dc_kwh: float = Field(
        ..., description="Energia DC anual estimada para esta configuração, em kWh, antes de perdas do sistema"
    )


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
    panel_capacity_watts: float | None = Field(
        default=None,
        description=(
            "Potência nominal do painel de referência usado pelo Google para "
            "estimar produção, em watts. Nulo quando o Google não informa "
            "essa dimensão para a coordenada consultada."
        ),
    )
    panel_width_meters: float | None = Field(
        default=None,
        description=(
            "Largura do painel de referência usado pelo Google, em metros. "
            "Nulo quando o Google não informa essa dimensão."
        ),
    )
    panel_height_meters: float | None = Field(
        default=None,
        description=(
            "Altura do painel de referência usado pelo Google, em metros. "
            "Nulo quando o Google não informa essa dimensão."
        ),
    )
    panel_configs: list[SolarPanelConfig] = Field(
        default_factory=list,
        description=(
            "Configurações candidatas de quantidade de painéis e sua energia "
            "DC anual estimada, ordenadas pela ordem retornada pelo Google. "
            "Lista vazia quando o Google não retorna configurações para a "
            "coordenada consultada."
        ),
    )
