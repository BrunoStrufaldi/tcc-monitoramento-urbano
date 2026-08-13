from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.log_sistema import LogSistema
from app.schemas.log_sistema import LogSistemaResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[LogSistemaResponse])
def listar_logs(
    db: Session = Depends(get_db),
    nivel: str | None = None,
    modulo: str | None = None,
    evento_id: int | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[LogSistema]:
    query = db.query(LogSistema)

    if nivel:
        query = query.filter(LogSistema.nivel == nivel.upper())
    if modulo:
        query = query.filter(LogSistema.modulo == modulo)
    if evento_id is not None:
        query = query.filter(LogSistema.evento_id == evento_id)

    return query.order_by(LogSistema.criado_em.desc()).limit(limite).all()
