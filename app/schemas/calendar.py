"""DTOs públicos da capability de Calendar (`/v1/calendar/...`)

Expostos pelo router
transformação de dados Google -> ambiente Solier acontece
em `app.infrastructure.google.calendar`
"""

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class ConnectResponse(BaseModel):
    """Endereço da tela de consentimento do Google para o técnico"""

    authorization_url: str = Field(..., description="URL para onde levar o técnico autorizar o acesso ao Calendar")


class ConnectionStatus(BaseModel):
    """Resultado do callback do consentimento"""

    status: Literal["connected"] = Field(..., description="Conta Google do técnico conectada")


class Interval(BaseModel):
    """Intervalo de tempo"""

    start: AwareDatetime = Field(..., description="Início do intervalo")
    end: AwareDatetime = Field(..., description="Fim do intervalo")


class Availability(BaseModel):
    """Ocupação e janelas livres do técnico em um período"""

    busy: list[Interval] = Field(..., description="Intervalos ocupados, como informados pelo Google")
    free: list[Interval] = Field(..., description="Janelas livres dentro do período consultado")


class EventCreate(BaseModel):
    """Evento a criar na agenda principal do técnico (sem convidados e sem e-mail)"""

    title: str = Field(..., min_length=1, description="Título do evento")
    start: AwareDatetime = Field(..., description="Início (ISO 8601 com fuso)")
    end: AwareDatetime = Field(..., description="Fim (ISO 8601 com fuso)")
    time_zone: str | None = Field(default=None, description="Fuso IANA do evento (ex.: America/Sao_Paulo)")
    location: str | None = Field(default=None, description="Local")
    description: str | None = Field(default=None, description="Descrição")

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.start >= self.end:
            raise ValueError("start precisa ser anterior a end")
        return self


class EventUpdate(BaseModel):
    """Atualização parcial de um evento: só os campos enviados mudam"""

    title: str | None = Field(default=None, min_length=1, description="Novo título")
    start: AwareDatetime | None = Field(default=None, description="Novo início (ISO 8601 com fuso)")
    end: AwareDatetime | None = Field(default=None, description="Novo fim (ISO 8601 com fuso)")
    time_zone: str | None = Field(default=None, description="Fuso IANA aplicado ao início e ao fim enviados")
    location: str | None = Field(default=None, description="Novo local")
    description: str | None = Field(default=None, description="Nova descrição")

    @model_validator(mode="after")
    def _at_least_one_consistent_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("informe ao menos um campo para atualizar")
        if self.time_zone is not None and self.start is None and self.end is None:
            raise ValueError("time_zone exige start ou end")
        if self.start is not None and self.end is not None and self.start >= self.end:
            raise ValueError("start precisa ser anterior a end")
        return self


class Event(BaseModel):
    """Evento da agenda principal do técnico"""

    event_id: str = Field(..., description="Identificador do evento no Google")
    title: str | None = Field(default=None, description="Título")
    start: str | None = Field(
        default=None,
        description="Início como o Google informa: ISO 8601 com fuso, ou só a data em eventos de dia inteiro",
    )
    end: str | None = Field(default=None, description="Fim, no mesmo formato de `start`")
    time_zone: str | None = Field(default=None, description="Fuso IANA do evento, quando informado")
    location: str | None = Field(default=None, description="Local")
    status: str | None = Field(default=None, description="Estado no Google (confirmed, tentative, cancelled)")
    html_link: str | None = Field(default=None, description="Link do evento na interface do Google Calendar")


class EventList(BaseModel):
    """Página de eventos"""

    events: list[Event] = Field(..., description="Eventos do período, ordenados por início")
    next_page_token: str | None = Field(default=None, description="Token da próxima página (omitido na última)")
