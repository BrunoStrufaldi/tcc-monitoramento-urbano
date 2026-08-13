from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LogSistemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nivel: str
    modulo: str
    mensagem: str
    evento_id: int | None
    contexto: dict[str, Any] | None
    ip_origem: str | None
    criado_em: datetime
