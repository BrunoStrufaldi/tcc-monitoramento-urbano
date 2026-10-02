from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
