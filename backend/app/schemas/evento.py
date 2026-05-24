from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventoBase(BaseModel):
    tipo: str = Field(..., max_length=100, examples=["transito", "alagamento", "incendio"])
    descricao: str | None = None
    criticidade: str | None = Field(None, max_length=50, examples=["baixa", "media", "alta", "critica"])
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    status: str | None = Field(default="ativo", max_length=50)
    confiabilidade: float = Field(default=0.0, ge=0, le=1)
    fonte: str | None = Field(None, max_length=100, examples=["api", "sensor", "manual"])


class EventoCreate(EventoBase):
    pass


class EventoUpdate(BaseModel):
    tipo: str | None = Field(None, max_length=100)
    descricao: str | None = None
    criticidade: str | None = Field(None, max_length=50)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    status: str | None = Field(None, max_length=50)
    confiabilidade: float | None = Field(None, ge=0, le=1)
    fonte: str | None = Field(None, max_length=100)


class EventoResponse(EventoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
