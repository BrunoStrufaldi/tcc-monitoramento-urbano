from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fonte_dados import FonteDadosResponse
from app.schemas.localizacao import LocalizacaoResponse
from app.schemas.regiao import RegiaoResponse

SEVERIDADES = Literal["baixa", "media", "alta", "critica"]
STATUS_EVENTO = Literal["ativo", "em_analise"]


class EventoBase(BaseModel):
    titulo: str = Field(..., max_length=200)
    descricao: str | None = None
    tipo: str = Field(..., max_length=50, examples=["transito", "alagamento"])
    severidade: SEVERIDADES = "media"
    status: STATUS_EVENTO = "ativo"
    regiao_id: int | None = None
    fonte_id: int | None = None
    confianca: Decimal | None = Field(None, ge=0, le=1)


class EventoResponse(EventoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    localizacao_id: int
    latitude: float
    longitude: float
    detectado_em: datetime
    criado_em: datetime
    atualizado_em: datetime
    localizacao: LocalizacaoResponse | None = None
    regiao: RegiaoResponse | None = None
    fonte: FonteDadosResponse | None = None
