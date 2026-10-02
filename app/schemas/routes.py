"""DTOs públicos da capability de rotas (`/v1/routes/...`)

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece
em `app.infrastructure.google.routes.adapter`
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TravelMode = Literal["DRIVE", "WALK"]


class Waypoint(BaseModel):
    """Um ponto de origem ou destino da rota"""

    latitude: float = Field(..., ge=-90, le=90, description="Latitude do ponto")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude do ponto")


class RouteRequest(BaseModel):
    """Pedido de cálculo de rotas entre dois pontos"""

    origin: Waypoint = Field(..., description="Ponto de partida")
    destination: Waypoint = Field(..., description="Ponto de chegada")
    travel_mode: TravelMode = Field(default="DRIVE", description="Meio de transporte: DRIVE (carro) ou WALK (a pé)")
    departure_at: datetime | None = Field(
        default=None,
        description=(
            "Horário de partida (ISO 8601; sem fuso vale UTC), usado no trânsito previsto de DRIVE. "
            "Omitido: agora. O Google não aceita horário no passado"
        ),
    )
    avoid_tolls: bool = Field(default=False, description="Evitar pedágios (só DRIVE)")
    avoid_highways: bool = Field(default=False, description="Evitar rodovias (só DRIVE)")
    alternatives: bool = Field(default=True, description="Incluir rotas alternativas, até 3 no total")


class RouteOption(BaseModel):
    """Uma rota possível entre a origem e o destino"""

    duration_seconds: int = Field(..., description="Duração estimada, em segundos (com trânsito previsto em DRIVE)")
    distance_meters: int = Field(..., description="Distância, em metros")
    encoded_polyline: str | None = Field(
        default=None, description="Traçado da rota no formato Encoded Polyline do Google (precisão 5)"
    )


class RouteResponse(BaseModel):
    """Rotas calculadas, da recomendada pelo Google para as alternativas"""

    routes: list[RouteOption] = Field(
        ..., description="Rotas, na ordem devolvida pelo Google (a primeira é a principal)"
    )
