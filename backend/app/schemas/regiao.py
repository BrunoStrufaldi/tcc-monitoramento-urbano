from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RegiaoCreate(BaseModel):
    nome: str = Field(..., max_length=120)
    codigo: str | None = Field(None, max_length=32)
    descricao: str | None = None
    poligono_geojson: dict[str, Any] | None = None


class RegiaoUpdate(BaseModel):
    nome: str | None = Field(None, max_length=120)
    codigo: str | None = Field(None, max_length=32)
    descricao: str | None = None
    poligono_geojson: dict[str, Any] | None = None
    ativo: bool | None = None


class RegiaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    codigo: str | None
    descricao: str | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
