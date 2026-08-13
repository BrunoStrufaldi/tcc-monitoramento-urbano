from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.evento import Evento
from app.models.localizacao import Localizacao
from app.schemas.evento import EventoCreate, EventoResponse, EventoUpdate
from app.schemas.localizacao import LocalizacaoCreate

router = APIRouter(prefix="/eventos", tags=["eventos"])

_EVENTO_LOAD_OPTIONS = (
    joinedload(Evento.localizacao),
    joinedload(Evento.regiao),
    joinedload(Evento.fonte),
)


def _resolver_localizacao(db: Session, payload: EventoCreate) -> Localizacao:
    if payload.localizacao_id:
        localizacao = db.get(Localizacao, payload.localizacao_id)
        if not localizacao:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Localização não encontrada",
            )
        return localizacao

    dados = payload.localizacao
    if dados is None:
        if payload.latitude is None or payload.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Coordenadas obrigatórias quando localização não é informada",
            )
        dados = LocalizacaoCreate(
            latitude=payload.latitude,
            longitude=payload.longitude,
            regiao_id=payload.regiao_id,
        )

    localizacao = Localizacao(**dados.model_dump())
    db.add(localizacao)
    db.flush()
    return localizacao


@router.get("", response_model=list[EventoResponse])
def listar_eventos(
    db: Session = Depends(get_db),
    status_filtro: str | None = Query(None, alias="status"),
    tipo: str | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[Evento]:
    query = db.query(Evento).options(*_EVENTO_LOAD_OPTIONS)

    if status_filtro:
        query = query.filter(Evento.status == status_filtro)
    if tipo:
        query = query.filter(Evento.tipo == tipo)

    return query.order_by(Evento.detectado_em.desc()).limit(limite).all()


@router.get("/{evento_id}", response_model=EventoResponse)
def obter_evento(evento_id: int, db: Session = Depends(get_db)) -> Evento:
    evento = (
        db.query(Evento)
        .options(*_EVENTO_LOAD_OPTIONS)
        .filter(Evento.id == evento_id)
        .first()
    )
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    return evento


@router.post("", response_model=EventoResponse, status_code=status.HTTP_201_CREATED)
def criar_evento(payload: EventoCreate, db: Session = Depends(get_db)) -> Evento:
    localizacao = _resolver_localizacao(db, payload)
    dados_evento = payload.model_dump(
        exclude={"localizacao", "localizacao_id", "latitude", "longitude"}
    )
    evento = Evento(**dados_evento, localizacao_id=localizacao.id)
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return (
        db.query(Evento)
        .options(*_EVENTO_LOAD_OPTIONS)
        .filter(Evento.id == evento.id)
        .first()
    )


@router.patch("/{evento_id}", response_model=EventoResponse)
def atualizar_evento(
    evento_id: int,
    payload: EventoUpdate,
    db: Session = Depends(get_db),
) -> Evento:
    evento = db.get(Evento, evento_id)
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(evento, campo, valor)

    db.commit()
    db.refresh(evento)
    return (
        db.query(Evento)
        .options(*_EVENTO_LOAD_OPTIONS)
        .filter(Evento.id == evento.id)
        .first()
    )


@router.delete("/{evento_id}", response_model=EventoResponse)
def remover_evento(
    evento_id: int,
    db: Session = Depends(get_db),
) -> dict:
    evento = (
        db.query(Evento)
        .options(*_EVENTO_LOAD_OPTIONS)
        .filter(Evento.id == evento_id)
        .first()
    )
    if not evento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")

    dados = EventoResponse.model_validate(evento, from_attributes=True).model_dump()
    db.delete(evento)
    db.commit()
    return dados
