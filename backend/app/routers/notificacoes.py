from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.models.notificacao import Notificacao
from app.schemas.notificacao import (
    NotificacaoCreate,
    NotificacaoResponse,
    NotificacaoUpdate,
)

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


@router.get("", response_model=list[NotificacaoResponse])
def listar_notificacoes(
    db: Session = Depends(get_db),
    evento_id: int | None = None,
    canal: str | None = None,
    status_filtro: str | None = Query(None, alias="status"),
    limite: int = Query(100, ge=1, le=500),
) -> list[Notificacao]:
    query = db.query(Notificacao)

    if evento_id is not None:
        query = query.filter(Notificacao.evento_id == evento_id)
    if canal:
        query = query.filter(Notificacao.canal == canal)
    if status_filtro:
        query = query.filter(Notificacao.status == status_filtro)

    return query.order_by(Notificacao.criado_em.desc()).limit(limite).all()


@router.get("/{notificacao_id}", response_model=NotificacaoResponse)
def obter_notificacao(
    notificacao_id: int,
    db: Session = Depends(get_db),
) -> Notificacao:
    notificacao = db.get(Notificacao, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )
    return notificacao


@router.post("", response_model=NotificacaoResponse, status_code=status.HTTP_201_CREATED)
def criar_notificacao(payload: NotificacaoCreate, db: Session = Depends(get_db)) -> Notificacao:
    evento = db.get(Evento, payload.evento_id)
    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado",
        )

    notificacao = Notificacao(**payload.model_dump())
    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.patch("/{notificacao_id}", response_model=NotificacaoResponse)
def atualizar_notificacao(
    notificacao_id: int,
    payload: NotificacaoUpdate,
    db: Session = Depends(get_db),
) -> Notificacao:
    notificacao = db.get(Notificacao, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(notificacao, campo, valor)

    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_como_lida(
    notificacao_id: int,
    db: Session = Depends(get_db),
) -> Notificacao:
    notificacao = db.get(Notificacao, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )

    notificacao.status = "lida"
    notificacao.lida_em = datetime.now()
    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.patch("/{notificacao_id}/arquivar", response_model=NotificacaoResponse)
def arquivar_notificacao(
    notificacao_id: int,
    db: Session = Depends(get_db),
) -> Notificacao:
    notificacao = db.get(Notificacao, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )

    notificacao.status = "arquivada"
    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.delete("/{notificacao_id}", response_model=NotificacaoResponse)
def remover_notificacao(
    notificacao_id: int,
    db: Session = Depends(get_db),
) -> dict:
    notificacao = db.get(Notificacao, notificacao_id)
    if not notificacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )

    dados = NotificacaoResponse.model_validate(notificacao, from_attributes=True).model_dump()
    db.delete(notificacao)
    db.commit()
    return dados
