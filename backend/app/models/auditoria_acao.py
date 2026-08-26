from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditoriaAcao(Base):
    __tablename__ = "auditoria_acoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    acao: Mapped[str] = mapped_column(String(120), nullable=False)
    # Identificador histórico: não usa FK para sobreviver à remoção do evento.
    evento_id: Mapped[int | None] = mapped_column(index=True)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
