from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evento import Evento


class OcorrenciaExterna(Base):
    """Rastreia registros já processados de fontes externas (ex.: GeoSampa/Defesa
    Civil) para não duplicar evento a cada nova consulta ao mesmo dataset."""

    __tablename__ = "ocorrencias_externas"
    __table_args__ = (UniqueConstraint("fonte", "identificador_externo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fonte: Mapped[str] = mapped_column(String(60), nullable=False)
    identificador_externo: Mapped[str] = mapped_column(String(80), nullable=False)
    evento_id: Mapped[int | None] = mapped_column(ForeignKey("eventos.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evento: Mapped["Evento | None"] = relationship()
