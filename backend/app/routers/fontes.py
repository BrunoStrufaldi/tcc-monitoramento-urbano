from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fonte_dados import FonteDados
from app.schemas.fonte_dados import FonteDadosCreate, FonteDadosResponse, FonteDadosUpdate
from app.services.weather_source import obter_condicoes_atuais, obter_qualidade_do_ar

router = APIRouter(prefix="/fontes", tags=["fontes"])


@router.get("/tempo-real/clima")
def clima_tempo_real(
    latitude: float = Query(-23.55052, ge=-90, le=90),
    longitude: float = Query(-46.633308, ge=-180, le=180),
) -> dict:
    """Condições atuais de uma fonte meteorológica externa e pública."""
    return obter_condicoes_atuais(latitude, longitude)


@router.get("/tempo-real/ar")
def qualidade_ar_tempo_real(
    latitude: float = Query(-23.55052, ge=-90, le=90),
    longitude: float = Query(-46.633308, ge=-180, le=180),
) -> dict:
    """Qualidade atual do ar de fonte externa, aberta e sem credenciais."""
    return obter_qualidade_do_ar(latitude, longitude)


@router.get("", response_model=list[FonteDadosResponse])
def listar_fontes(
    db: Session = Depends(get_db),
    tipo: str | None = None,
    ativo: bool | None = None,
    limite: int = Query(100, ge=1, le=500),
) -> list[FonteDados]:
    query = db.query(FonteDados)
    if tipo:
        query = query.filter(FonteDados.tipo == tipo)
    if ativo is not None:
        query = query.filter(FonteDados.ativo == ativo)
    return query.order_by(FonteDados.nome).limit(limite).all()


@router.get("/{fonte_id}", response_model=FonteDadosResponse)
def obter_fonte(fonte_id: int, db: Session = Depends(get_db)) -> FonteDados:
    fonte = db.get(FonteDados, fonte_id)
    if not fonte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada")
    return fonte


@router.post("", response_model=FonteDadosResponse, status_code=status.HTTP_201_CREATED)
def criar_fonte(payload: FonteDadosCreate, db: Session = Depends(get_db)) -> FonteDados:
    fonte = FonteDados(**payload.model_dump())
    db.add(fonte)
    db.commit()
    db.refresh(fonte)
    return fonte


@router.patch("/{fonte_id}", response_model=FonteDadosResponse)
def atualizar_fonte(
    fonte_id: int,
    payload: FonteDadosUpdate,
    db: Session = Depends(get_db),
) -> FonteDados:
    fonte = db.get(FonteDados, fonte_id)
    if not fonte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada")

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(fonte, campo, valor)

    db.commit()
    db.refresh(fonte)
    return fonte


@router.delete("/{fonte_id}", response_model=FonteDadosResponse)
def remover_fonte(
    fonte_id: int,
    db: Session = Depends(get_db),
) -> dict:
    fonte = db.get(FonteDados, fonte_id)
    if not fonte:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fonte não encontrada")

    dados = FonteDadosResponse.model_validate(fonte, from_attributes=True).model_dump()
    db.delete(fonte)
    db.commit()
    return dados
