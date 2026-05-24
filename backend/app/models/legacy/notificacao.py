from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.evento import Evento


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    canal: Mapped[str] = mapped_column(String(20), default="painel")
    destinatario: Mapped[str | None] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    tentativas: Mapped[int] = mapped_column(SmallInteger, default=0)
    erro_detalhe: Mapped[str | None] = mapped_column(Text)
    agendada_para: Mapped[datetime | None] = mapped_column(DateTime)
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime)
    lida_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    evento: Mapped["Evento"] = relationship(back_populates="notificacoes")
