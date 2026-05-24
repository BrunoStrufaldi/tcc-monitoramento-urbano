from datetime import datetime

from sqlalchemy import DateTime, Float, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Evento(Base):
    """Modelo principal de eventos urbanos — fase fundação do TCC."""

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    criticidade: Mapped[str | None] = mapped_column(String(50))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    status: Mapped[str | None] = mapped_column(String(50), default="ativo")
    confiabilidade: Mapped[float] = mapped_column(Float, default=0.0)
    fonte: Mapped[str | None] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
