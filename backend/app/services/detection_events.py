"""Persiste um evento a partir de uma detecção YOLO já validada pelo servidor.

Usado tanto pela confirmação manual (upload no painel) quanto pela detecção
contínua em câmera ao vivo — as duas produzem o mesmo tipo de evidência
auditável e disparam o mesmo broadcast em tempo real.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.broadcast import schedule_coroutine
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.routers.tempo_real import _broadcast
from app.schemas.evento import EventoResponse
from app.services.evidence_annotation import annotate_evidence
from app.ws_manager import manager as ws_manager
from ml.detector import Deteccao

_EVIDENCIAS_DIR = Path(__file__).resolve().parents[1] / "data" / "evidencias"
_DISPLAY_NAMES = {
    "veiculo": "Veículo",
    "onibus": "Ônibus",
    "caminhao": "Caminhão",
    "transito": "Trânsito",
}


def _fonte(db: Session, nome: str, descricao: str) -> FonteDados:
    source = db.query(FonteDados).filter(FonteDados.tipo == "yolo", FonteDados.nome == nome).first()
    if source:
        return source
    source = FonteDados(nome=nome, tipo="yolo", descricao=descricao)
    db.add(source)
    db.flush()
    return source


def registrar_deteccao(
    db: Session,
    deteccao: Deteccao,
    conteudo_imagem: bytes,
    latitude: float,
    longitude: float,
    *,
    fonte_nome: str = "GX YOLO",
    fonte_descricao: str = "Evidências visuais geradas por validação computacional.",
    modelo_ia: str = "YOLO11 (inferência repetida no servidor)",
    origem: str = "camera_ou_upload",
    deteccoes_para_anotar: list[Deteccao] | None = None,
) -> Evento:
    """Cria localização, evento e evidência, e propaga via WebSocket/SSE."""
    _EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    identificador = uuid.uuid4().hex
    nome_original = identificador + "-original.jpg"
    (_EVIDENCIAS_DIR / nome_original).write_bytes(conteudo_imagem)
    nome_arquivo = identificador + "-yolo.jpg"
    largura = altura = None
    try:
        anotada, largura, altura = annotate_evidence(conteudo_imagem, deteccoes_para_anotar or [deteccao])
        (_EVIDENCIAS_DIR / nome_arquivo).write_bytes(anotada)
    except Exception:
        # A inferência já foi concluída; se a anotação visual falhar, o original
        # continua sendo uma evidência válida e auditável.
        nome_arquivo = nome_original

    rotulo = _DISPLAY_NAMES.get(deteccao.nome, deteccao.nome.replace("_", " ").title())
    observacao_objeto = deteccao.tipo == "observacao_visual"
    titulo = ("Observação YOLO: " + rotulo + " detectado") if observacao_objeto else ("Possível " + rotulo + " detectado pelo YOLO")
    descricao = (
        "Detecção visual produzida pelo modelo YOLO em imagem real. "
        "Isto comprova a presença do objeto na captura, não um incidente urbano."
        if observacao_objeto else
        "Sinal visual produzido pelo modelo YOLO em imagem real; ocorrência mantida em análise até validação operacional."
    )

    localizacao = Localizacao(latitude=latitude, longitude=longitude)
    db.add(localizacao)
    db.flush()
    source = _fonte(db, fonte_nome, fonte_descricao)
    evento = Evento(
        titulo=titulo,
        descricao=descricao,
        tipo=deteccao.tipo,
        severidade=deteccao.severidade,
        status="em_analise",
        confianca=deteccao.confianca,
        localizacao_id=localizacao.id,
        fonte_id=source.id,
    )
    db.add(evento)
    db.flush()
    db.add(EvidenciaVisual(
        evento_id=evento.id,
        tipo="imagem",
        caminho_arquivo=nome_arquivo,
        fonte_id=source.id,
        modelo_ia=modelo_ia,
        classe_detectada=deteccao.nome,
        confianca=deteccao.confianca,
        largura_px=largura,
        altura_px=altura,
        metadados={
            "origem": origem,
            "validado_no_servidor": True,
            "classe_modelo": deteccao.classe_modelo,
            "bbox": deteccao.bbox,
            "arquivo_original": nome_original,
            "sha256_original": hashlib.sha256(conteudo_imagem).hexdigest(),
            "observacao_nao_e_incidente": observacao_objeto,
        },
    ))
    db.commit()
    resultado = db.query(Evento).options(
        joinedload(Evento.localizacao), joinedload(Evento.regiao), joinedload(Evento.fonte)
    ).filter(Evento.id == evento.id).first()

    payload = EventoResponse.model_validate(resultado, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(_broadcast("evento_criado", payload))
    schedule_coroutine(ws_manager.broadcast_evento("evento_criado", payload))
    return resultado


def publicar_evento(db: Session, evento_id: int, *, tipo_mensagem: str = "evento_atualizado") -> None:
    """Propaga um evento já persistido para WS/SSE (ex.: após recalcular a fusão)."""
    evento = db.query(Evento).options(
        joinedload(Evento.localizacao), joinedload(Evento.regiao), joinedload(Evento.fonte)
    ).filter(Evento.id == evento_id).first()
    if not evento:
        return
    payload = EventoResponse.model_validate(evento, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(_broadcast(tipo_mensagem, payload))
    schedule_coroutine(ws_manager.broadcast_evento(tipo_mensagem, payload))
