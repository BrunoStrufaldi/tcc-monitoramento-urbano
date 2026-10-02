"""Rotas de visão computacional do MotSP.

Só consulta e teste: nenhuma rota daqui grava evento ou evidência. Eventos nascem
da detecção contínua nas câmeras (``services/live_detection.py`` e
``services/flood_detection.py``)."""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.detector import (  # noqa: E402
    CLASSES_URBANAS,
    detectar_imagem_real,
    detectar_incidentes_imagem,
    status_detector,
    status_incident_detector,
)

router = APIRouter(prefix="/deteccao", tags=["deteccao-yolo"])


class DeteccaoResponse(BaseModel):
    classe_id: int
    nome: str
    confianca: float = Field(ge=0, le=1)
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int]
    classe_modelo: str | None = None


def _serializar(deteccoes: list) -> list[DeteccaoResponse]:
    return [
        DeteccaoResponse(
            classe_id=item.classe_id,
            nome=item.nome,
            confianca=item.confianca,
            severidade=item.severidade,
            tipo=item.tipo,
            bbox=item.bbox,
            classe_modelo=item.classe_modelo,
        )
        for item in deteccoes
    ]


@router.get("/classes")
def listar_classes() -> dict:
    return {
        "aviso": "As classes urbanas são mapeamentos configuráveis. Os pesos COCO padrão não detectam alagamento, fumaça ou incêndio.",
        "classes": [
            {"id": key, "nome": value["nome"], "severidade": value["severidade"], "tipo": value["tipo"]}
            for key, value in CLASSES_URBANAS.items()
        ]
    }


@router.get("/status")
def obter_status_detector() -> dict:
    """Estado dos dois modelos, para o testador de YOLO do painel."""
    resultado = status_detector()
    resultado["incidente"] = status_incident_detector()
    resultado["min_veiculos_transito"] = settings.gx_transito_min_veiculos
    return resultado


@router.post("/imagem", response_model=list[DeteccaoResponse])
async def detectar_em_imagem(
    file: UploadFile = File(...),
    confianca_minima: float = Query(0.45, ge=0.05, le=0.95),
):
    """Executa inferência YOLO sobre upload temporário, que é removido ao final."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Apenas imagens são aceitas (image/*)")
    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="A imagem enviada está vazia")
    if len(conteudo) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="A imagem deve ter no máximo 10 MB")

    extensao = Path(file.filename or "imagem.jpg").suffix or ".jpg"
    caminho_temporario = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as arquivo:
            arquivo.write(conteudo)
            caminho_temporario = arquivo.name
        deteccoes = detectar_imagem_real(caminho_temporario, confianca_minima)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if caminho_temporario:
            try:
                os.unlink(caminho_temporario)
            except FileNotFoundError:
                pass
    return _serializar(deteccoes)


@router.post("/incidente", response_model=list[DeteccaoResponse])
async def detectar_incidente_em_imagem(
    file: UploadFile = File(...),
    confianca_minima: float = Query(0.3, ge=0.05, le=0.95),
):
    """Roda o modelo dedicado a alagamento (GX_YOLO_INCIDENT_MODEL) sobre um
    upload de teste — não passa pelo pipeline de eventos/evidências, é só pra
    validar a inferência isoladamente."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Apenas imagens são aceitas (image/*)")
    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="A imagem enviada está vazia")
    if len(conteudo) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="A imagem deve ter no máximo 10 MB")

    extensao = Path(file.filename or "imagem.jpg").suffix or ".jpg"
    caminho_temporario = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extensao) as arquivo:
            arquivo.write(conteudo)
            caminho_temporario = arquivo.name
        deteccoes = detectar_incidentes_imagem(caminho_temporario, confianca_minima)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if caminho_temporario:
            try:
                os.unlink(caminho_temporario)
            except FileNotFoundError:
                pass
    return _serializar(deteccoes)
