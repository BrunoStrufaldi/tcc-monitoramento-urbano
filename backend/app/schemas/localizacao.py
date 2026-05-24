from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocalizacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    regiao_id: int | None
    latitude: float
    longitude: float
    endereco: str | None
    bairro: str | None
    cidade: str | None
    cep: str | None
    precisao_metros: float | None
    referencia: str | None
    criado_em: datetime
    atualizado_em: datetime


class LocalizacaoCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    regiao_id: int | None = None
    endereco: str | None = None
    bairro: str | None = None
    cidade: str | None = "São Paulo"
    cep: str | None = None
    precisao_metros: float | None = None
    referencia: str | None = None
