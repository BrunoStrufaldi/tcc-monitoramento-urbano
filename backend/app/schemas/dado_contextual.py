from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DadoContextualCreate(BaseModel):
    evento_id: int | None = None
    regiao_id: int | None = None
    fonte_id: int | None = None
    categoria: str = Field(..., max_length=60)
    chave: str = Field(..., max_length=80)
    valor_texto: str | None = None
    valor_numerico: float | None = None
    unidade: str | None = Field(None, max_length=30)


class DadoContextualResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int | None
    regiao_id: int | None
    fonte_id: int | None
    categoria: str
    chave: str
    valor_texto: str | None
    valor_numerico: float | None
    unidade: str | None
    coletado_em: datetime
    criado_em: datetime
