from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegiaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    codigo: str | None
    descricao: str | None
    criado_em: datetime
    atualizado_em: datetime
