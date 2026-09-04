"""Consulta de eventos. Eventos nascem da detecção automática
(``services/detection_events.py``); o painel é somente leitura e não cria,
altera nem remove evento por requisição."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models.evento import Evento
from app.schemas.evento import EventoResponse
from app.services.event_retention import limite_da_janela


router = APIRouter(prefix="/eventos", tags=["eventos"])

_EVENTO_LOAD_OPTIONS = (
    joinedload(Evento.localizacao),
    joinedload(Evento.regiao),
    joinedload(Evento.fonte),
)


@router.get("", response_model=list[EventoResponse])
def listar_eventos(
    db: Session = Depends(get_db),
    status_filtro: str | None = Query(None, alias="status"),
    tipo: str | None = None,
    limite: int = Query(100, ge=1, le=500),
    janela_minutos: int | None = Query(None, ge=0, description="0 = sem janela (histórico completo)"),
) -> list[Evento]:
    query = db.query(Evento).options(*_EVENTO_LOAD_OPTIONS)

    # Quadro em tempo real: por padrão só retorna eventos detectados dentro da
    # janela configurada. janela_minutos=0 desliga o corte (auditoria/debug).
    minutos = settings.gx_evento_janela_minutos if janela_minutos is None else janela_minutos
    if minutos > 0:
        query = query.filter(Evento.detectado_em >= limite_da_janela(minutos))

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
