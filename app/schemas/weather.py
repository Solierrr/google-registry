"""DTOs públicos da capability de clima (`/v1/weather/...`)

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece
em `app.infrastructure.google.weather.adapter`
"""

from datetime import datetime

from pydantic import BaseModel, Field


class HourlyWeather(BaseModel):
    """Previsão do clima para a hora que contém o instante consultado"""

    interval_start: datetime = Field(..., description="Início da hora prevista (UTC)")
    interval_end: datetime = Field(..., description="Fim da hora prevista (UTC)")
    precipitation_probability_percent: int | None = Field(
        default=None, description="Probabilidade de precipitação na hora, de 0 a 100 (omitida se o Google não informar)"
    )
    condition: str | None = Field(
        default=None, description="Descrição da condição do tempo, no idioma pedido (omitida se o Google não informar)"
    )
