from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CANAL_NOTIFICACAO = Literal["painel", "push", "email", "sms", "webhook"]
STATUS_NOTIFICACAO = Literal["pendente", "enviada", "falha", "lida"]


class NotificacaoCreate(BaseModel):
    evento_id: int
    canal: CANAL_NOTIFICACAO = "painel"
    destinatario: str | None = Field(None, max_length=200)
    titulo: str = Field(..., max_length=200)
    mensagem: str
    agendada_para: datetime | None = None


class NotificacaoUpdate(BaseModel):
    canal: CANAL_NOTIFICACAO | None = None
    destinatario: str | None = None
    titulo: str | None = Field(None, max_length=200)
    mensagem: str | None = None
    agendada_para: datetime | None = None


class NotificacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evento_id: int
    canal: str
    destinatario: str | None
    titulo: str
    mensagem: str
    status: str
    tentativas: int
    erro_detalhe: str | None
    agendada_para: datetime | None
    enviada_em: datetime | None
    lida_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime
