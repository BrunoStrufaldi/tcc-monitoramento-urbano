from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dado_contextual import DadoContextual
    from app.models.evidencia_visual import EvidenciaVisual
    from app.models.fonte_dados import FonteDados
    from app.models.localizacao import Localizacao
    from app.models.log_sistema import LogSistema
    from app.models.notificacao import Notificacao
    from app.models.regiao import Regiao


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    severidade: Mapped[str] = mapped_column(String(20), default="media")
    status: Mapped[str] = mapped_column(String(30), default="ativo")
    localizacao_id: Mapped[int] = mapped_column(ForeignKey("localizacoes.id"))
    regiao_id: Mapped[int | None] = mapped_column(ForeignKey("regioes.id"))
    fonte_id: Mapped[int | None] = mapped_column(ForeignKey("fontes_dados.id"))
    confianca: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    detectado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    localizacao: Mapped["Localizacao"] = relationship(back_populates="eventos")
    regiao: Mapped["Regiao | None"] = relationship(back_populates="eventos")
    fonte: Mapped["FonteDados | None"] = relationship(back_populates="eventos")
    evidencias: Mapped[list["EvidenciaVisual"]] = relationship(back_populates="evento")
    dados_contextuais: Mapped[list["DadoContextual"]] = relationship(back_populates="evento")
    notificacoes: Mapped[list["Notificacao"]] = relationship(back_populates="evento")
    logs: Mapped[list["LogSistema"]] = relationship(back_populates="evento")

    @property
    def latitude(self) -> float:
        return self.localizacao.latitude

    @property
    def longitude(self) -> float:
        return self.localizacao.longitude
