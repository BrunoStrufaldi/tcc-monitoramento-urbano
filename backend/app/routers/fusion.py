from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.schemas.fusion import ComponenteConfiabilidadeResponse, ConfiabilidadeResponse
from app.services.data_fusion_service import aplicar_fusao_evento
from app.models.usuario import Usuario
from app.security import record_audit, require_operator

router = APIRouter(prefix="/fusion", tags=["data-fusion"])


def _resultado_para_response(
    resultado,
    evento: Evento,
    *,
    persistido: bool,
) -> ConfiabilidadeResponse:
    confianca_db = float(evento.confianca) if evento.confianca is not None else None
    return ConfiabilidadeResponse(
        evento_id=resultado.evento_id,
        confiabilidade=resultado.confiabilidade,
        nivel=resultado.nivel,
        componentes=[
            ComponenteConfiabilidadeResponse(
                nome=c.nome,
                pontuacao=c.pontuacao,
                peso=c.peso,
                contribuicao=c.contribuicao,
                detalhe=c.detalhe,
            )
            for c in resultado.componentes
        ],
        confianca_registrada=confianca_db,
        persistido=persistido,
        calculado_em=datetime.now(timezone.utc),
    )


@router.get("/eventos/{evento_id}/confiabilidade", response_model=ConfiabilidadeResponse)
def obter_confiabilidade(evento_id: int, db: Session = Depends(get_db)) -> ConfiabilidadeResponse:
    try:
        resultado, evento = aplicar_fusao_evento(db, evento_id, persistir=False)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    return _resultado_para_response(resultado, evento, persistido=False)


@router.post("/eventos/{evento_id}/recalcular", response_model=ConfiabilidadeResponse)
def recalcular_confiabilidade(
    evento_id: int,
    persistir: bool = Query(True, description="Grava score em eventos.confianca"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_operator),
) -> ConfiabilidadeResponse:
    try:
        resultado, evento = aplicar_fusao_evento(db, evento_id, persistir=persistir)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    response = _resultado_para_response(resultado, evento, persistido=persistir)
    record_audit(db, usuario_id=user.id, acao="FUSION_RECALCULAR", evento_id=evento_id, resultado="sucesso", detalhes={"persistido": persistir})
    return response


@router.post("/recalcular-todos", response_model=list[ConfiabilidadeResponse])
def recalcular_todos(
    persistir: bool = Query(True),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_operator),
) -> list[ConfiabilidadeResponse]:
    ids = [row[0] for row in db.query(Evento.id).limit(limite).all()]
    respostas: list[ConfiabilidadeResponse] = []
    for evento_id in ids:
        try:
            resultado, evento = aplicar_fusao_evento(db, evento_id, persistir=persistir)
            respostas.append(_resultado_para_response(resultado, evento, persistido=persistir))
        except ValueError:
            continue
    record_audit(db, usuario_id=user.id, acao="FUSION_RECALCULAR_TODOS", evento_id=None, resultado="sucesso", detalhes={"limite": limite, "quantidade": len(respostas), "persistido": persistir})
    return respostas
