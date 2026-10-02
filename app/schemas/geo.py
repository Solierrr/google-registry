from pydantic import BaseModel, Field


class TimezoneResponse(BaseModel):
    """Fuso horário de uma coordenada"""

    timezone_id: str = Field(..., description="Identificador IANA do fuso (ex.: America/Manaus)")
    utc_offset_seconds: int = Field(
        ..., description="Deslocamento em relação ao UTC, em segundos, no instante consultado (positivo a leste)"
    )
