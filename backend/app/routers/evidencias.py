from pathlib import Path

"""Consulta de evidências. As evidências são gravadas pela detecção
(``services/detection_events.py``), nunca por requisição do painel."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evidencia_visual import EvidenciaVisual
from app.schemas.evidencia_visual import EvidenciaVisualResponse

router = APIRouter(prefix="/evidencias", tags=["evidencias"])
_EVIDENCIAS_DIR = Path(__file__).resolve().parents[1] / "data" / "evidencias"


@router.get("/arquivo/{nome_arquivo}")
def obter_arquivo(nome_arquivo: str) -> FileResponse:
    """Entrega uma evidência local sem permitir travessia de diretórios."""
    caminho = _EVIDENCIAS_DIR / Path(nome_arquivo).name
    if not caminho.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado")
    return FileResponse(caminho)


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
