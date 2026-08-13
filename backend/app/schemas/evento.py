from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fonte_dados import FonteDadosResponse
from app.schemas.localizacao import LocalizacaoCreate, LocalizacaoResponse
from app.schemas.regiao import RegiaoResponse

SEVERIDADES = Literal["baixa", "media", "alta", "critica"]
STATUS_EVENTO = Literal["ativo", "em_analise", "resolvido"]


class EventoBase(BaseModel):
    titulo: str = Field(..., max_length=200)
    descricao: str | None = None
    tipo: str = Field(..., max_length=50, examples=["transito", "incendio", "alagamento"])
    severidade: SEVERIDADES = "media"
    status: STATUS_EVENTO = "ativo"
    regiao_id: int | None = None
    fonte_id: int | None = None
    confianca: Decimal | None = Field(None, ge=0, le=1)


class EventoCreate(EventoBase):
    localizacao_id: int | None = None
    localizacao: LocalizacaoCreate | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def validar_localizacao(self) -> "EventoCreate":
        tem_coords = self.latitude is not None and self.longitude is not None
        if not self.localizacao_id and not self.localizacao and not tem_coords:
            raise ValueError(
                "Informe localizacao_id, localizacao ou latitude/longitude"
            )
        return self


class EventoUpdate(BaseModel):
    titulo: str | None = Field(None, max_length=200)
    descricao: str | None = None
    tipo: str | None = Field(None, max_length=50)
    severidade: SEVERIDADES | None = None
    status: STATUS_EVENTO | None = None
    regiao_id: int | None = None
    fonte_id: int | None = None
    confianca: Decimal | None = Field(None, ge=0, le=1)
    resolvido_em: datetime | None = None


class EventoResponse(EventoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    localizacao_id: int
    latitude: float
    longitude: float
    detectado_em: datetime
    resolvido_em: datetime | None = None
    criado_em: datetime
    atualizado_em: datetime
    localizacao: LocalizacaoResponse | None = None
    regiao: RegiaoResponse | None = None
    fonte: FonteDadosResponse | None = None
