from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evento import Evento


class LogSistema(Base):
    __tablename__ = "logs_sistema"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nivel: Mapped[str] = mapped_column(String(20), default="INFO")
    modulo: Mapped[str] = mapped_column(String(80), nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    evento_id: Mapped[int | None] = mapped_column(ForeignKey("eventos.id", ondelete="SET NULL"))
    contexto: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_origem: Mapped[str | None] = mapped_column(String(45))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evento: Mapped["Evento | None"] = relationship(back_populates="logs")
