from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dado_contextual import DadoContextual
from app.schemas.dado_contextual import DadoContextualResponse

router = APIRouter(prefix="/dados-contextuais", tags=["dados_contextuais"])


@router.get("", response_model=list[DadoContextualResponse])
def listar_dados_contextuais(
    db: Session = Depends(get_db),
    evento_id: int | None = None,
    regiao_id: int | None = None,
    categoria: str | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[DadoContextual]:
    query = db.query(DadoContextual)
    if evento_id is not None:
        query = query.filter(DadoContextual.evento_id == evento_id)
    if regiao_id is not None:
        query = query.filter(DadoContextual.regiao_id == regiao_id)
    if categoria:
        query = query.filter(DadoContextual.categoria == categoria)
    return query.order_by(DadoContextual.coletado_em.desc()).limit(limite).all()


@router.get("/{dado_id}", response_model=DadoContextualResponse)
def obter_dado_contextual(
    dado_id: int,
    db: Session = Depends(get_db),
) -> DadoContextual:
    dado = db.get(DadoContextual, dado_id)
    if not dado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dado contextual não encontrado",
        )
    return dado
