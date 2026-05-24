from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.schemas.evento import EventoCreate, EventoResponse, EventoUpdate

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.get("", response_model=list[EventoResponse])
def listar_eventos(
    db: Session = Depends(get_db),
    status_filtro: str | None = Query(None, alias="status"),
    tipo: str | None = None,
    criticidade: str | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[Evento]:
    query = db.query(Evento)

    if status_filtro:
        query = query.filter(Evento.status == status_filtro)
    if tipo:
        query = query.filter(Evento.tipo == tipo)
    if criticidade:
        query = query.filter(Evento.criticidade == criticidade)

    return query.order_by(Evento.criado_em.desc()).limit(limite).all()


@router.get("/{evento_id}", response_model=EventoResponse)
def obter_evento(evento_id: int, db: Session = Depends(get_db)) -> Evento:
    evento = db.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    return evento


@router.post("", response_model=EventoResponse, status_code=status.HTTP_201_CREATED)
def criar_evento(payload: EventoCreate, db: Session = Depends(get_db)) -> Evento:
    evento = Evento(**payload.model_dump())
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


@router.put("/{evento_id}", response_model=EventoResponse)
def atualizar_evento(
    evento_id: int,
    payload: EventoUpdate,
    db: Session = Depends(get_db),
) -> Evento:
    evento = db.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")

    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(evento, campo, valor)

    db.commit()
    db.refresh(evento)
    return evento


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_evento(evento_id: int, db: Session = Depends(get_db)) -> None:
    evento = db.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    db.delete(evento)
    db.commit()
