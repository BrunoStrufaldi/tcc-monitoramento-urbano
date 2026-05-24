from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evento import Evento
    from app.models.regiao import Regiao


class Localizacao(Base):
    __tablename__ = "localizacoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regiao_id: Mapped[int | None] = mapped_column(ForeignKey("regioes.id"))
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    endereco: Mapped[str | None] = mapped_column(String(255))
    bairro: Mapped[str | None] = mapped_column(String(120))
    cidade: Mapped[str | None] = mapped_column(String(120), default="São Paulo")
    cep: Mapped[str | None] = mapped_column(String(12))
    precisao_metros: Mapped[float | None] = mapped_column(Float)
    referencia: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    regiao: Mapped["Regiao | None"] = relationship(back_populates="localizacoes")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="localizacao")
