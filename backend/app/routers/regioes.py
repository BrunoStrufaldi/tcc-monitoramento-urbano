from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.regiao import Regiao
from app.schemas.regiao import RegiaoResponse

router = APIRouter(prefix="/regioes", tags=["regioes"])


@router.get("", response_model=list[RegiaoResponse])
def listar_regioes(
    db: Session = Depends(get_db),
    ativo: bool | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[Regiao]:
    query = db.query(Regiao)
    if ativo is not None:
        query = query.filter(Regiao.ativo == ativo)
    return query.order_by(Regiao.nome).limit(limite).all()


@router.get("/{regiao_id}", response_model=RegiaoResponse)
def obter_regiao(regiao_id: int, db: Session = Depends(get_db)) -> Regiao:
    regiao = db.get(Regiao, regiao_id)
    if not regiao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Região não encontrada")
    return regiao
