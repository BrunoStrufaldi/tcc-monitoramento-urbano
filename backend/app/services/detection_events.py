"""Grava os eventos que vêm da detecção nas câmeras e avisa o painel."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.broadcast import schedule_coroutine
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.routers.tempo_real import _broadcast
from app.schemas.evento import EventoResponse
from app.services.cet_camera_catalog import CAMERAS
from app.services.data_fusion_service import CATEGORIA_CONTEXTO, aplicar_fusao_evento
from app.services.evidence_annotation import annotate_evidence
from app.ws_manager import manager as ws_manager
from ml.detector import Deteccao

_EVIDENCIAS_DIR = Path(__file__).resolve().parents[1] / "data" / "evidencias"
_DISPLAY_NAMES = {"transito": "Trânsito"}


@dataclass
class Analise:
    """O que a análise de uma imagem encontrou e precisa ir para o evento."""

    deteccao: Deteccao
    fonte_nome: str
    fonte_descricao: str
    modelo_ia: str
    origem: str
    deteccoes_para_anotar: list[Deteccao] | None = None
    # Dados de contexto do Data Fusion, no formato (chave, valor, unidade).
    contexto: list[tuple[str, float, str]] = field(default_factory=list)


def _agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fonte(db: Session, nome: str, descricao: str) -> FonteDados:
    source = db.query(FonteDados).filter(FonteDados.tipo == "yolo", FonteDados.nome == nome).first()
    if source:
        return source
    source = FonteDados(nome=nome, tipo="yolo", descricao=descricao)
    db.add(source)
    db.flush()
    return source


def preencher_enderecos_das_cameras(db: Session, tolerancia_graus: float = 1e-4) -> int:
    """Dá o nome da câmera às localizações sem endereço que ficam no ponto de uma câmera do catálogo.

    Serve para os eventos gravados antes de a detecção salvar o nome da câmera.
    """
    preenchidas = 0
    for localizacao in db.query(Localizacao).filter(Localizacao.endereco.is_(None)).all():
        camera = next((
            cam for cam in CAMERAS
            if abs(cam.latitude - localizacao.latitude) < tolerancia_graus
            and abs(cam.longitude - localizacao.longitude) < tolerancia_graus
        ), None)
        if camera:
            localizacao.endereco = camera.nome
            preenchidas += 1
    if preenchidas:
        db.commit()
    return preenchidas


def buscar_evento_no_ponto(
    db: Session,
    *,
    tipo: str,
    latitude: float,
    longitude: float,
    tolerancia_graus: float = 1e-4,
) -> Evento | None:
    """Devolve o evento aberto desse tipo no ponto da câmera, se existir."""
    return (
        db.query(Evento)
        .join(Localizacao, Evento.localizacao_id == Localizacao.id)
        .filter(
            Evento.tipo == tipo,
            Evento.status.in_(("em_analise", "ativo")),
            func.abs(Localizacao.latitude - latitude) < tolerancia_graus,
            func.abs(Localizacao.longitude - longitude) < tolerancia_graus,
        )
        .order_by(Evento.detectado_em.desc())
        .first()
    )


def _salvar_imagens(conteudo_imagem: bytes, deteccoes: list[Deteccao]) -> tuple[str, str, int | None, int | None]:
    """Grava a foto original e a foto com as caixas do YOLO."""
    _EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    identificador = uuid.uuid4().hex
    nome_original = identificador + "-original.jpg"
    (_EVIDENCIAS_DIR / nome_original).write_bytes(conteudo_imagem)
    nome_arquivo = identificador + "-yolo.jpg"
    largura = altura = None
    try:
        anotada, largura, altura = annotate_evidence(conteudo_imagem, deteccoes)
        (_EVIDENCIAS_DIR / nome_arquivo).write_bytes(anotada)
    except Exception:
        # Se der erro ao desenhar as caixas, a foto original continua valendo.
        nome_arquivo = nome_original
    return nome_arquivo, nome_original, largura, altura


def _nova_evidencia(
    evento_id: int,
    fonte_id: int,
    deteccao: Deteccao,
    conteudo_imagem: bytes,
    *,
    modelo_ia: str,
    origem: str,
    deteccoes_para_anotar: list[Deteccao] | None,
) -> EvidenciaVisual:
    nome_arquivo, nome_original, largura, altura = _salvar_imagens(
        conteudo_imagem, deteccoes_para_anotar or [deteccao]
    )
    return EvidenciaVisual(
        evento_id=evento_id,
        tipo="imagem",
        caminho_arquivo=nome_arquivo,
        fonte_id=fonte_id,
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
        },
    )


def _apagar_arquivos(evidencia: EvidenciaVisual) -> None:
    nomes = {evidencia.caminho_arquivo, (evidencia.metadados or {}).get("arquivo_original")}
    for nome in nomes:
        if nome:
            (_EVIDENCIAS_DIR / nome).unlink(missing_ok=True)


def _gravar_contexto(db: Session, evento_id: int, contexto: list[tuple[str, float, str]]) -> None:
    for chave, valor, unidade in contexto:
        db.add(DadoContextual(
            evento_id=evento_id,
            categoria=CATEGORIA_CONTEXTO,
            chave=chave,
            valor_numerico=valor,
            unidade=unidade,
        ))


def criar_evento(
    db: Session,
    analise: Analise,
    conteudo_imagem: bytes,
    latitude: float,
    longitude: float,
    endereco: str | None = None,
) -> Evento:
    """Cria um evento novo, grava o contexto, calcula a fusão e avisa o painel."""
    evento = registrar_deteccao(
        db,
        analise.deteccao,
        conteudo_imagem,
        latitude,
        longitude,
        fonte_nome=analise.fonte_nome,
        fonte_descricao=analise.fonte_descricao,
        modelo_ia=analise.modelo_ia,
        origem=analise.origem,
        deteccoes_para_anotar=analise.deteccoes_para_anotar,
        endereco=endereco,
        publicar=False,
    )
    _gravar_contexto(db, evento.id, analise.contexto)
    db.commit()
    aplicar_fusao_evento(db, evento.id, persistir=True)
    publicar_evento(db, evento.id, tipo_mensagem="evento_criado")
    return evento


def atualizar_evento(
    db: Session,
    evento: Evento,
    analise: Analise,
    conteudo_imagem: bytes,
    endereco: str | None = None,
) -> Evento:
    """Atualiza um evento que já existe com o resultado do ciclo atual.

    O evento continua com o mesmo número, então não aparece repetido no mapa.
    A foto e os dados de contexto antigos são trocados pelos novos e a fusão é
    recalculada. Assim um evento em análise pode virar ativo e um ativo pode
    voltar para análise.
    """
    for evidencia in list(evento.evidencias):
        _apagar_arquivos(evidencia)
        db.delete(evidencia)
    db.query(DadoContextual).filter(
        DadoContextual.evento_id == evento.id,
        DadoContextual.categoria == CATEGORIA_CONTEXTO,
    ).delete(synchronize_session=False)

    source = _fonte(db, analise.fonte_nome, analise.fonte_descricao)
    db.add(_nova_evidencia(
        evento.id, source.id, analise.deteccao, conteudo_imagem,
        modelo_ia=analise.modelo_ia, origem=analise.origem,
        deteccoes_para_anotar=analise.deteccoes_para_anotar,
    ))
    _gravar_contexto(db, evento.id, analise.contexto)
    evento.detectado_em = _agora()
    evento.severidade = analise.deteccao.severidade
    if endereco and evento.localizacao and not evento.localizacao.endereco:
        evento.localizacao.endereco = endereco
    db.commit()
    # Descarta as listas que estão na memória para a fusão ler o que foi gravado.
    db.expire(evento)
    aplicar_fusao_evento(db, evento.id, persistir=True)
    publicar_evento(db, evento.id)
    return evento


def registrar_deteccao(
    db: Session,
    deteccao: Deteccao,
    conteudo_imagem: bytes,
    latitude: float,
    longitude: float,
    *,
    fonte_nome: str = "MotSP YOLO",
    fonte_descricao: str = "Evidências visuais geradas por validação computacional.",
    modelo_ia: str = "YOLO11 (inferência repetida no servidor)",
    origem: str = "camera_continua",
    deteccoes_para_anotar: list[Deteccao] | None = None,
    endereco: str | None = None,
    publicar: bool = True,
) -> Evento:
    """Cria a localização, o evento e a evidência, e avisa o painel."""
    rotulo = _DISPLAY_NAMES.get(deteccao.nome, deteccao.nome.replace("_", " ").title())
    titulo = "Possível " + rotulo + " detectado pelo YOLO"
    descricao = (
        "Sinal visual produzido pelo modelo YOLO em imagem real; ocorrência mantida "
        "em análise até a fusão de dados atingir o limiar de confiabilidade."
    )

    # O endereço é o nome da câmera, que é o que o painel mostra na busca por rua.
    localizacao = Localizacao(latitude=latitude, longitude=longitude, endereco=endereco)
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
    db.add(_nova_evidencia(
        evento.id, source.id, deteccao, conteudo_imagem,
        modelo_ia=modelo_ia, origem=origem, deteccoes_para_anotar=deteccoes_para_anotar,
    ))
    db.commit()
    resultado = db.query(Evento).options(
        joinedload(Evento.localizacao), joinedload(Evento.fonte)
    ).filter(Evento.id == evento.id).first()

    if publicar:
        payload = EventoResponse.model_validate(resultado, from_attributes=True).model_dump(mode="json")
        schedule_coroutine(_broadcast("evento_criado", payload))
        schedule_coroutine(ws_manager.broadcast_evento("evento_criado", payload))
    return resultado


def publicar_evento(db: Session, evento_id: int, *, tipo_mensagem: str = "evento_atualizado") -> None:
    """Avisa o painel sobre um evento que já está gravado."""
    evento = db.query(Evento).options(
        joinedload(Evento.localizacao), joinedload(Evento.fonte)
    ).filter(Evento.id == evento_id).first()
    if not evento:
        return
    payload = EventoResponse.model_validate(evento, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(_broadcast(tipo_mensagem, payload))
    schedule_coroutine(ws_manager.broadcast_evento(tipo_mensagem, payload))
