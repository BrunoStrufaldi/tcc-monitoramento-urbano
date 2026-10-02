from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
