"""Monitoramento automático de ocorrências oficiais (GeoSampa/Defesa Civil/CET) —
alagamento, queda de árvore e acidente de trânsito, sem depender de relato
humano nem de câmera.

Nenhuma delas tem classe visual no YOLO/COCO padrão, e não existe (verificado
consultando o serviço de verdade) uma API pública de "aconteceu agora" para
essas ocorrências em SP — nem para as três camadas do GeoSampa nem para o CGE
(não tem API pública, só HTML) nem para o Waze for Cities (exige convênio
formal da prefeitura com o Google, não é algo que dá pra obter sozinho). O que
existe são datasets oficiais recarregados em lote (GeoSampa/Defesa Civil/CET,
ver ``geosampa_source.py``), com coordenada real mas defasagem de semanas a
poucos meses entre o ocorrido e a publicação. Por isso o loop aqui:

1. Consulta periodicamente esses datasets, descartando o que já foi visto
   (tabela ``ocorrencias_externas``, evita duplicar evento pro mesmo registro).
2. Para cada registro novo, busca o clima atual naquele ponto exato e, se
   houver uma câmera pública da CET conhecida a poucos km (``cet_camera_catalog``),
   roda o YOLO nela também. Só alagamento e árvore caída têm classe no modelo
   dedicado (``GX_YOLO_INCIDENT_MODEL``) — nesse caso é confirmação visual
   direta. Para acidente de trânsito (e para os outros dois sem o modelo
   dedicado disponível) o YOLO/COCO padrão só reconhece objetos, então vira
   sinal indireto ("a câmera está ativa e capturou algo ali perto"), NUNCA
   confirma o incidente sozinho, registrado com confiança deliberadamente
   limitada.
3. Roda o mesmo motor de Data Fusion do resto do sistema com o que houver
   disponível (IA do passo 2, se existiu; clima do passo 2; fonte oficial).
   Só confirma (status -> ativo) e dispara uma Notificacao de verdade quando a
   confiabilidade calculada passa de ``GX_CONFIRMACAO_CONFIANCA_MINIMA``.
   Abaixo disso, o evento fica em ``em_analise`` — visível no painel, mas não
   "confirmado" nem notificado.

Roda em thread própria; eventos e notificações são publicados no loop
assíncrono principal via ``app.broadcast.schedule_coroutine``.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy.orm import Session, joinedload

from app.broadcast import schedule_coroutine
from app.config import settings
from app.database import SessionLocal
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.models.notificacao import Notificacao
from app.models.ocorrencia_externa import OcorrenciaExterna
from app.routers.tempo_real import _broadcast
from app.schemas.evento import EventoResponse
from app.schemas.notificacao import NotificacaoResponse
from app.services import cet_camera_catalog, geosampa_source
from app.services.data_fusion_service import aplicar_fusao_evento
from app.services.weather_source import obter_condicoes_atuais
from app.ws_manager import manager as ws_manager
from ml.detector import (
    detectar_imagem_real,
    detectar_incidentes_imagem,
    status_detector,
    status_incident_detector,
)

# Sinal indireto: a câmera não confirma o incidente (YOLO/COCO não reconhece
# alagamento nem árvore caída), só que há atividade real captada por perto.
# O teto evita que isso pese como se fosse uma confirmação visual do incidente.
_CONFIANCA_MAXIMA_SINAL_INDIRETO = 0.5

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop_event = threading.Event()

_FONTES = {
    "geosampa_alagamento": {
        "tipo_evento": "alagamento",
        "titulo": "Possível alagamento — ocorrência registrada pela Defesa Civil",
        "severidade": "alta",
        "chave_clima": "precipitacao_mm_h",
        "unidade_clima": "mm/h",
    },
    "geosampa_queda_arvore": {
        "tipo_evento": "arvore_caida",
        "titulo": "Possível queda de árvore — ocorrência registrada pela Defesa Civil",
        "severidade": "media",
        "chave_clima": "vento_kmh",
        "unidade_clima": "km/h",
    },
    "geosampa_acidente_transito": {
        "tipo_evento": "acidente_transito",
        "titulo": "Acidente de trânsito — ocorrência levantada pela CET",
        "severidade": "media",
        "chave_clima": "precipitacao_mm_h",
        "unidade_clima": "mm/h",
    },
}


def _fonte_defesa_civil(db: Session) -> FonteDados:
    source = db.query(FonteDados).filter(FonteDados.tipo == "api", FonteDados.nome == "Defesa Civil (GeoSampa)").first()
    if source:
        return source
    source = FonteDados(
        nome="Defesa Civil (GeoSampa)",
        tipo="api",
        descricao="Ocorrências oficiais da Defesa Civil de SP, via WFS público do GeoSampa.",
    )
    db.add(source)
    db.flush()
    return source


def _fonte_cet(db: Session) -> FonteDados:
    source = db.query(FonteDados).filter(FonteDados.tipo == "api", FonteDados.nome == "CET (GeoSampa)").first()
    if source:
        return source
    source = FonteDados(
        nome="CET (GeoSampa)",
        tipo="api",
        descricao="Acidentes de trânsito levantados pela CET, via WFS público do GeoSampa.",
    )
    db.add(source)
    db.flush()
    return source


def _severidade_acidente(ocorrencia: dict) -> str:
    fatais = ocorrencia.get("fatais") or 0
    feridos = ocorrencia.get("feridos") or 0
    if fatais > 0:
        return "critica"
    if feridos > 0:
        return "alta"
    return "media"


def _ja_processado(db: Session, fonte: str, identificador: str) -> bool:
    existe = db.query(OcorrenciaExterna).filter(
        OcorrenciaExterna.fonte == fonte,
        OcorrenciaExterna.identificador_externo == identificador,
    ).first()
    return existe is not None


def _publicar(db: Session, evento_id: int, tipo_mensagem: str) -> None:
    evento = db.query(Evento).options(
        joinedload(Evento.localizacao), joinedload(Evento.regiao), joinedload(Evento.fonte)
    ).filter(Evento.id == evento_id).first()
    if not evento:
        return
    payload = EventoResponse.model_validate(evento, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(_broadcast(tipo_mensagem, payload))
    schedule_coroutine(ws_manager.broadcast_evento(tipo_mensagem, payload))


def _confirmar_e_notificar(db: Session, evento: Evento) -> None:
    evento.status = "ativo"
    db.commit()
    notificacao = Notificacao(
        evento_id=evento.id,
        canal="painel",
        titulo=evento.titulo,
        mensagem=evento.descricao or evento.titulo,
        status="pendente",
    )
    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)
    notif_payload = NotificacaoResponse.model_validate(notificacao, from_attributes=True).model_dump(mode="json")
    schedule_coroutine(ws_manager.broadcast_evento("notificacao_criada", notif_payload))


def _buscar_corroboracao_visual(db: Session, evento_id: int, latitude: float, longitude: float, tipo_esperado: str) -> None:
    """Se houver câmera CET conhecida por perto, roda o modelo de incidentes nela.

    Com o modelo dedicado (``GX_YOLO_INCIDENT_MODEL``) disponível e a classe
    detectada batendo com o tipo da ocorrência, isso é confirmação visual
    direta. Sem o modelo (ou sem bater a classe), cai para o comportamento
    antigo: YOLO/COCO só enxerga objetos, então vira sinal indireto fraco
    (nunca confirma o incidente sozinho, ver módulo)."""
    incident_disponivel = status_incident_detector().get("disponivel")
    coco_disponivel = status_detector().get("disponivel")
    if not incident_disponivel and not coco_disponivel:
        return

    camera = cet_camera_catalog.camera_mais_proxima(latitude, longitude, settings.gx_camera_busca_raio_km)
    if camera is None:
        return

    caminho = ""
    try:
        resposta = httpx.get(camera.snapshot_url, timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (GX-TCC context-monitor)"})
        resposta.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as arquivo:
            arquivo.write(resposta.content)
            caminho = arquivo.name

        if incident_disponivel:
            deteccoes_incidente = detectar_incidentes_imagem(caminho, settings.yolo_threshold)
            confirmacao = next((item for item in deteccoes_incidente if item.nome == tipo_esperado), None)
            if confirmacao is not None:
                db.add(EvidenciaVisual(
                    evento_id=evento_id,
                    tipo="imagem",
                    modelo_ia="YOLO11 (modelo de incidentes GX — confirmação direta)",
                    classe_detectada=confirmacao.nome,
                    confianca=confirmacao.confianca,
                    metadados={
                        "sinal_indireto": False,
                        "camera_id": camera.id,
                        "camera_nome": camera.nome,
                    },
                ))
                return

        if not coco_disponivel:
            return
        deteccoes = detectar_imagem_real(caminho, settings.yolo_threshold)
    except (httpx.HTTPError, RuntimeError):
        return
    finally:
        if caminho:
            Path(caminho).unlink(missing_ok=True)

    if not deteccoes:
        return

    melhor = deteccoes[0]
    db.add(EvidenciaVisual(
        evento_id=evento_id,
        tipo="imagem",
        modelo_ia="YOLO11 (câmera pública próxima — sinal indireto)",
        classe_detectada=melhor.nome,
        confianca=min(melhor.confianca, _CONFIANCA_MAXIMA_SINAL_INDIRETO),
        metadados={
            "sinal_indireto": True,
            "aviso": "Não confirma o incidente; a câmera não reconhece alagamento/queda de árvore, só objetos.",
            "camera_id": camera.id,
            "camera_nome": camera.nome,
            "classe_bruta_confianca": melhor.confianca,
        },
    ))


def _processar_ocorrencia(db: Session, fonte_chave: str, ocorrencia: dict) -> None:
    config = _FONTES[fonte_chave]
    identificador = ocorrencia["identificador"]
    if _ja_processado(db, fonte_chave, identificador):
        return

    latitude = ocorrencia["latitude"]
    longitude = ocorrencia["longitude"]
    e_acidente = fonte_chave == "geosampa_acidente_transito"

    localizacao = Localizacao(latitude=latitude, longitude=longitude, bairro=ocorrencia.get("subprefeitura"))
    db.add(localizacao)
    db.flush()

    if e_acidente:
        fonte = _fonte_cet(db)
        descricao = (
            "Registro oficial da CET (GeoSampa), acidente de "
            f"{ocorrencia.get('data_ocorrencia') or 'data não informada'} em "
            f"{ocorrencia.get('logradouro') or 'logradouro não informado'}"
            + (f" ({ocorrencia['tipo_acidente']})" if ocorrencia.get("tipo_acidente") else "")
            + f". Feridos: {int(ocorrencia.get('feridos') or 0)}, óbitos: {int(ocorrencia.get('fatais') or 0)}. "
            "Corroborado com o clima atual no ponto antes de confirmar."
        )
        severidade = _severidade_acidente(ocorrencia)
    else:
        fonte = _fonte_defesa_civil(db)
        descricao = (
            "Registro oficial da Defesa Civil (SIGRC/GeoSampa), ocorrência de "
            f"{ocorrencia.get('data_ocorrencia') or 'data não informada'} em "
            f"{ocorrencia.get('subprefeitura') or 'subprefeitura não informada'}. "
            "Corroborado com o clima atual no ponto antes de confirmar."
        )
        severidade = config["severidade"]

    evento = Evento(
        titulo=config["titulo"],
        descricao=descricao,
        tipo=config["tipo_evento"],
        severidade=severidade,
        status="em_analise",
        localizacao_id=localizacao.id,
        fonte_id=fonte.id,
    )
    db.add(evento)
    db.flush()

    condicoes = obter_condicoes_atuais(latitude, longitude)
    if condicoes.get("disponivel"):
        valor = condicoes.get("chuva_mm") if config["chave_clima"] == "precipitacao_mm_h" else condicoes.get("vento_kmh")
        if valor is not None:
            db.add(DadoContextual(
                evento_id=evento.id,
                categoria="clima",
                chave=config["chave_clima"],
                valor_numerico=float(valor),
                unidade=config["unidade_clima"],
            ))

    _buscar_corroboracao_visual(db, evento.id, latitude, longitude, config["tipo_evento"])

    db.add(OcorrenciaExterna(fonte=fonte_chave, identificador_externo=identificador, evento_id=evento.id))
    db.commit()

    resultado, evento_atualizado = aplicar_fusao_evento(db, evento.id, persistir=True)
    _publicar(db, evento.id, "evento_criado")

    if resultado.confiabilidade >= settings.gx_confirmacao_confianca_minima:
        _confirmar_e_notificar(db, evento_atualizado)
        _publicar(db, evento.id, "evento_atualizado")
        logger.info("Ocorrência confirmada e notificada: %s (%.0f%%)", config["tipo_evento"], resultado.confiabilidade * 100)
    else:
        logger.info("Ocorrência registrada, aguardando corroboração: %s (%.0f%%)", config["tipo_evento"], resultado.confiabilidade * 100)


def _checar_geosampa() -> None:
    data_minima = (datetime.now(UTC) - timedelta(days=settings.gx_geosampa_janela_dias)).strftime("%Y-%m-%d")

    for fonte_chave, buscar in (
        ("geosampa_alagamento", geosampa_source.buscar_alagamentos),
        ("geosampa_queda_arvore", geosampa_source.buscar_quedas_de_arvore),
        ("geosampa_acidente_transito", geosampa_source.buscar_acidentes_transito),
    ):
        try:
            ocorrencias = buscar(data_minima)
        except Exception:
            logger.exception("Falha ao consultar GeoSampa (%s)", fonte_chave)
            continue

        with SessionLocal() as db:
            for ocorrencia in ocorrencias:
                try:
                    _processar_ocorrencia(db, fonte_chave, ocorrencia)
                except Exception:
                    db.rollback()
                    logger.exception("Falha ao processar ocorrência %s de %s", ocorrencia.get("identificador"), fonte_chave)


def _loop(interval: float) -> None:
    while not _stop_event.is_set():
        _checar_geosampa()
        _stop_event.wait(interval)


def iniciar() -> None:
    global _thread
    _stop_event.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(settings.gx_geosampa_interval_seconds,),
        daemon=True,
        name="gx-geosampa-monitor",
    )
    _thread.start()
    logger.info("Monitoramento de ocorrências GeoSampa iniciado (intervalo %ss)", settings.gx_geosampa_interval_seconds)


def parar() -> None:
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=5)
