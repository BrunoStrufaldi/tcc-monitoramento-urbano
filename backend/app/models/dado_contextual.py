from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evento import Evento
    from app.models.fonte_dados import FonteDados
    from app.models.regiao import Regiao


class DadoContextual(Base):
    __tablename__ = "dados_contextuais"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int | None] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    regiao_id: Mapped[int | None] = mapped_column(ForeignKey("regioes.id"))
    fonte_id: Mapped[int | None] = mapped_column(ForeignKey("fontes_dados.id"))
    categoria: Mapped[str] = mapped_column(String(60), nullable=False)
    chave: Mapped[str] = mapped_column(String(80), nullable=False)
    valor_texto: Mapped[str | None] = mapped_column(Text)
    valor_numerico: Mapped[float | None] = mapped_column(Float)
    unidade: Mapped[str | None] = mapped_column(String(30))
    coletado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evento: Mapped["Evento | None"] = relationship(back_populates="dados_contextuais")
    regiao: Mapped["Regiao | None"] = relationship(back_populates="dados_contextuais")
    fonte: Mapped["FonteDados | None"] = relationship(back_populates="dados_contextuais")
