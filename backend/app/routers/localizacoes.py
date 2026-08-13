from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.models.localizacao import Localizacao
from app.schemas.localizacao import LocalizacaoCreate, LocalizacaoResponse, LocalizacaoUpdate

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


@router.post("", response_model=LocalizacaoResponse, status_code=status.HTTP_201_CREATED)
def criar_localizacao(
    payload: LocalizacaoCreate,
    db: Session = Depends(get_db),
) -> Localizacao:
    localizacao = Localizacao(**payload.model_dump())
    db.add(localizacao)
    db.commit()
    db.refresh(localizacao)
    return localizacao


@router.patch("/{localizacao_id}", response_model=LocalizacaoResponse)
def atualizar_localizacao(
    localizacao_id: int,
    payload: LocalizacaoUpdate,
    db: Session = Depends(get_db),
) -> Localizacao:
    localizacao = db.get(Localizacao, localizacao_id)
    if not localizacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Localização não encontrada",
        )

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(localizacao, campo, valor)

    db.commit()
    db.refresh(localizacao)
    return localizacao


@router.delete("/{localizacao_id}", response_model=LocalizacaoResponse)
def remover_localizacao(
    localizacao_id: int,
    db: Session = Depends(get_db),
) -> dict:
    localizacao = db.get(Localizacao, localizacao_id)
    if not localizacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Localização não encontrada",
        )

    tem_eventos = db.query(Evento).filter(Evento.localizacao_id == localizacao_id).first()
    if tem_eventos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Existem eventos vinculados a esta localização",
        )

    dados = LocalizacaoResponse.model_validate(localizacao, from_attributes=True).model_dump()
    db.delete(localizacao)
    db.commit()
    return dados
