from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.schemas.evidencia_visual import EvidenciaVisualCreate, EvidenciaVisualResponse

router = APIRouter(prefix="/evidencias", tags=["evidencias"])


@router.get("", response_model=list[EvidenciaVisualResponse])
def listar_evidencias(
    db: Session = Depends(get_db),
    evento_id: int | None = None,
    tipo: str | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[EvidenciaVisual]:
    query = db.query(EvidenciaVisual)
    if evento_id is not None:
        query = query.filter(EvidenciaVisual.evento_id == evento_id)
    if tipo:
        query = query.filter(EvidenciaVisual.tipo == tipo)
    return query.order_by(EvidenciaVisual.capturado_em.desc()).limit(limite).all()


@router.get("/{evidencia_id}", response_model=EvidenciaVisualResponse)
def obter_evidencia(
    evidencia_id: int,
    db: Session = Depends(get_db),
) -> EvidenciaVisual:
    evidencia = db.get(EvidenciaVisual, evidencia_id)
    if not evidencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidência não encontrada",
        )
    return evidencia


@router.post("", response_model=EvidenciaVisualResponse, status_code=status.HTTP_201_CREATED)
def criar_evidencia(
    payload: EvidenciaVisualCreate,
    db: Session = Depends(get_db),
) -> EvidenciaVisual:
    evento = db.get(Evento, payload.evento_id)
    if not evento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento não encontrado",
        )

    evidencia = EvidenciaVisual(**payload.model_dump())
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)
    return evidencia


@router.delete("/{evidencia_id}", response_model=EvidenciaVisualResponse)
def remover_evidencia(
    evidencia_id: int,
    db: Session = Depends(get_db),
) -> dict:
    evidencia = db.get(EvidenciaVisual, evidencia_id)
    if not evidencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidência não encontrada",
        )

    dados = EvidenciaVisualResponse.model_validate(evidencia, from_attributes=True).model_dump()
    db.delete(evidencia)
    db.commit()
    return dados
