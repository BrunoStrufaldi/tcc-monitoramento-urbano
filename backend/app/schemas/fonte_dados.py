from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
