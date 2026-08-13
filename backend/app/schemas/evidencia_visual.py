from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenciaVisualCreate(BaseModel):
    evento_id: int
    fonte_id: int | None = None
    tipo: str = Field(default="imagem", max_length=20)
    caminho_arquivo: str | None = Field(None, max_length=500)
    url_externa: str | None = Field(None, max_length=500)
    modelo_ia: str | None = Field(None, max_length=80)
    classe_detectada: str | None = Field(None, max_length=80)
    confianca: Decimal | None = Field(None, ge=0, le=1)
    largura_px: int | None = None
    altura_px: int | None = None
    metadados: dict[str, Any] | None = None


class EvidenciaVisualResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    fonte_id: int | None
    tipo: str
    caminho_arquivo: str | None
    url_externa: str | None
    modelo_ia: str | None
    classe_detectada: str | None
    confianca: Decimal | None
    largura_px: int | None
    altura_px: int | None
    metadados: dict[str, Any] | None
    capturado_em: datetime
    criado_em: datetime
