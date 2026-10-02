from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LocalizacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    regiao_id: int | None
    latitude: float
    longitude: float
    endereco: str | None
    bairro: str | None
    cidade: str | None
    cep: str | None
    precisao_metros: float | None
    referencia: str | None
    criado_em: datetime
    atualizado_em: datetime
