from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evento import Evento
    from app.models.fonte_dados import FonteDados


class EvidenciaVisual(Base):
    __tablename__ = "evidencias_visuais"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    fonte_id: Mapped[int | None] = mapped_column(ForeignKey("fontes_dados.id"))
    tipo: Mapped[str] = mapped_column(String(20), default="imagem")
    caminho_arquivo: Mapped[str | None] = mapped_column(String(500))
    url_externa: Mapped[str | None] = mapped_column(String(500))
    modelo_ia: Mapped[str | None] = mapped_column(String(80))
    classe_detectada: Mapped[str | None] = mapped_column(String(80))
    confianca: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    largura_px: Mapped[int | None] = mapped_column(Integer)
    altura_px: Mapped[int | None] = mapped_column(Integer)
    metadados: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    capturado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evento: Mapped["Evento"] = relationship(back_populates="evidencias")
    fonte: Mapped["FonteDados | None"] = relationship(back_populates="evidencias")
