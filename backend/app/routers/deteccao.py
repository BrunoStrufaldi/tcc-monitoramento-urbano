"""Rotas de visão computacional para o centro operacional GX."""

import os
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.broadcast import schedule_coroutine
from app.config import settings
from app.database import get_db
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.fonte_dados import FonteDados
from app.routers.tempo_real import _broadcast
from app.schemas.evento import EventoResponse
from app.ws_manager import manager as ws_manager
from app.services.data_fusion_service import aplicar_fusao_evento
from app.services.detection_events import registrar_deteccao
from app.services.visual_validation import FrameResult, visual_validation_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.detector import (  # noqa: E402
    CLASSES_URBANAS,
    detectar_imagem,
    detectar_imagem_real,
    detectar_incidentes_imagem,
    detectar_video,
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


class DeteccaoRequest(BaseModel):
    """Parâmetros exclusivos da rota de demonstração."""

    num_deteccoes: int | None = Field(None, ge=1, le=10)


class VideoDeteccaoResponse(BaseModel):
    total_frames: int
    total_deteccoes: int
    resumo_classes: dict[str, int]


class FrameResponse(BaseModel):
    frame_id: str
    deteccoes: list[DeteccaoResponse]
    timestamp: str
    latencia_ms: int
    relevante: bool
    modo: str
    evidencia_id: int | None = None
    evento_id: int | None = None
    confianca_fusion: float | None = None


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


def _agendar_atualizacao(evento_id: int, db: Session) -> None:
    evento = db.query(Evento).options(joinedload(Evento.localizacao), joinedload(Evento.regiao), joinedload(Evento.fonte)).filter(Evento.id == evento_id).first()
    if not evento:
        return
    resultado = EventoResponse.model_validate(evento, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(_broadcast("evento_atualizado", resultado))
    schedule_coroutine(ws_manager.broadcast_evento("evento_atualizado", resultado))


def _fonte_yolo(db: Session) -> FonteDados:
    source = db.query(FonteDados).filter(FonteDados.tipo == "yolo", FonteDados.nome == "GX YOLO").first()
    if source:
        return source
    source = FonteDados(nome="GX YOLO", tipo="yolo", descricao="Evidências visuais geradas por validação computacional.")
    db.add(source)
    db.flush()
    return source


def _frame_response(result: FrameResult, *, evidence_id: int | None = None, event_id: int | None = None, confidence: float | None = None) -> FrameResponse:
    return FrameResponse(
        frame_id=result.frame_id,
        deteccoes=[DeteccaoResponse(**item.__dict__) for item in result.deteccoes],
        timestamp=result.timestamp,
        latencia_ms=result.latencia_ms,
        relevante=result.relevante,
        modo=result.modo,
        evidencia_id=evidence_id,
        evento_id=event_id,
        confianca_fusion=confidence,
    )


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
    """Estado do modelo, para que a interface não confunda demo com YOLO real."""
    resultado = status_detector()
    resultado["incidente"] = status_incident_detector()
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
    """Roda o modelo dedicado a alagamento/árvore caída (GX_YOLO_INCIDENT_MODEL)
    sobre um upload de teste — não passa pelo pipeline de eventos/evidências,
    é só pra validar a inferência isoladamente."""
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


@router.post("/frame", response_model=FrameResponse)
async def validar_frame(
    file: UploadFile = File(...),
    frame_id: str = Form(..., max_length=100),
    threshold: float | None = Form(None, ge=0.05, le=0.95),
    evento_id: int | None = Form(None),
    persistir: bool = Form(False),
    db: Session = Depends(get_db),
) -> FrameResponse:
    """Valida um frame; só registra evidência mediante consentimento explícito."""
    content = await file.read()
    try:
        result = visual_validation_service.validate_frame(content, file.content_type or "", frame_id, threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    evidence_id = None
    confidence = None
    if persistir and result.relevante:
        if evento_id is None:
            raise HTTPException(status_code=422, detail="evento_id é obrigatório para persistir evidência")
        event = db.get(Evento, evento_id)
        if not event:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
        detection = next((item for item in result.deteccoes if not item.duplicada), None)
        if detection:
            source = _fonte_yolo(db)
            evidence = EvidenciaVisual(
                evento_id=event.id, fonte_id=source.id, tipo="frame", modelo_ia="YOLO (" + result.modo + ")",
                classe_detectada=detection.nome, confianca=detection.confianca,
                metadados={"frame_id": frame_id, "bbox": detection.bbox, "latencia_ms": result.latencia_ms, "persistido_com_consentimento": True},
            )
            db.add(evidence)
            db.commit()
            db.refresh(evidence)
            evidence_id = evidence.id
            fusion, _ = aplicar_fusao_evento(db, event.id, persistir=True)
            confidence = fusion.confiabilidade
            _agendar_atualizacao(event.id, db)
    return _frame_response(result, evidence_id=evidence_id, event_id=evento_id if evidence_id else None, confidence=confidence)


@router.post("/confirmar", response_model=EventoResponse, status_code=status.HTTP_201_CREATED)
async def confirmar_deteccao(
    file: UploadFile = File(...),
    nome: str = Form(..., max_length=80),
    confianca: float = Form(..., ge=0, le=1),
    severidade: str = Form("media", pattern="^(baixa|media|alta|critica)$"),
    tipo: str = Form("mobilidade", max_length=50),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    db: Session = Depends(get_db),
) -> Evento:
    """Repete a inferência no servidor e registra uma observação auditável.

    Os campos enviados pelo cliente servem apenas para indicar a caixa escolhida.
    Classe, confiança, severidade e tipo gravados vêm da nova inferência YOLO.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="A confirmação exige uma imagem")
    conteudo = await file.read()
    if not conteudo or len(conteudo) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem vazia ou maior que 10 MB")

    try:
        resultado_frame = visual_validation_service.validate_frame(
            conteudo,
            file.content_type,
            "confirmacao-" + uuid.uuid4().hex,
            settings.yolo_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    deteccao = next((item for item in resultado_frame.deteccoes if item.nome == nome), None)
    if deteccao is None:
        deteccao = resultado_frame.deteccoes[0] if resultado_frame.deteccoes else None
    if deteccao is None:
        raise HTTPException(status_code=422, detail="O servidor não confirmou nenhuma detecção YOLO nesta imagem")

    return registrar_deteccao(db, deteccao, conteudo, latitude, longitude)


@router.post("/simular", response_model=list[DeteccaoResponse])
def simular_deteccao(payload: DeteccaoRequest | None = None):
    """Gera dados de demonstração. Não chama um modelo de IA."""
    quantidade = payload.num_deteccoes if payload else None
    return _serializar(detectar_imagem("simulacao_tcc", num_deteccoes=quantidade))


@router.post("/video", response_model=VideoDeteccaoResponse)
def detectar_em_video(num_frames: int = Query(30, ge=1, le=300)):
    """Fluxo de demonstração para frames; inferência real de vídeo é próxima etapa."""
    return VideoDeteccaoResponse(**detectar_video("video_simulado", frames_totais=num_frames))
