from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento
    from app.models.localizacao import Localizacao


class Regiao(Base):
    __tablename__ = "regioes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(32), unique=True)
    descricao: Mapped[str | None] = mapped_column(Text)
    poligono_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    localizacoes: Mapped[list["Localizacao"]] = relationship(back_populates="regiao")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="regiao")
    dados_contextuais: Mapped[list["DadoContextual"]] = relationship(back_populates="regiao")
