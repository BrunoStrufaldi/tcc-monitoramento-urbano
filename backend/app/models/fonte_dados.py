from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento
    from app.models.evidencia_visual import EvidenciaVisual


class FonteDados(Base):
    __tablename__ = "fontes_dados"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(500))
    descricao: Mapped[str | None] = mapped_column(Text)
    configuracao: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    eventos: Mapped[list["Evento"]] = relationship(back_populates="fonte")
    evidencias: Mapped[list["EvidenciaVisual"]] = relationship(back_populates="fonte")
    dados_contextuais: Mapped[list["DadoContextual"]] = relationship(back_populates="fonte")
