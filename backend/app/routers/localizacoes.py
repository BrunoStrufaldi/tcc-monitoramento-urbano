from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.localizacao import Localizacao
from app.schemas.localizacao import LocalizacaoResponse

router = APIRouter(prefix="/localizacoes", tags=["localizacoes"])


@router.get("", response_model=list[LocalizacaoResponse])
def listar_localizacoes(
    db: Session = Depends(get_db),
    regiao_id: int | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[Localizacao]:
    query = db.query(Localizacao)
    if regiao_id is not None:
        query = query.filter(Localizacao.regiao_id == regiao_id)
    return query.order_by(Localizacao.criado_em.desc()).limit(limite).all()


@router.get("/{localizacao_id}", response_model=LocalizacaoResponse)
def obter_localizacao(
    localizacao_id: int,
    db: Session = Depends(get_db),
) -> Localizacao:
    localizacao = db.get(Localizacao, localizacao_id)
    if not localizacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Localização não encontrada",
        )
    return localizacao
