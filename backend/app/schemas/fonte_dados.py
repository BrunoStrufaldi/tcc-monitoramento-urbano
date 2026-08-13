from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FonteDadosCreate(BaseModel):
    nome: str = Field(..., max_length=120)
    tipo: str = Field(..., max_length=50)
    endpoint: str | None = Field(None, max_length=500)
    descricao: str | None = None
    configuracao: dict[str, Any] | None = None


class FonteDadosUpdate(BaseModel):
    nome: str | None = Field(None, max_length=120)
    tipo: str | None = Field(None, max_length=50)
    endpoint: str | None = Field(None, max_length=500)
    descricao: str | None = None
    configuracao: dict[str, Any] | None = None
    ativo: bool | None = None


class FonteDadosResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tipo: str
    endpoint: str | None
    descricao: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
