"""Monitora as câmeras da CET-SP e detecta alagamento.

Funciona como o monitoramento de trânsito, mas usa o modelo de alagamento.
Quando ele encontra água na pista, o sistema também busca a chuva no local, o
aviso do INMET e o histórico de alagamento da via, e esses dados ajudam a
decidir se o alerta é confiável. Só roda se estiver ativado na configuração.
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
import threading
import time
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.dado_contextual import DadoContextual
from app.services import cet_camera_catalog
from app.services.data_fusion_service import CATEGORIA_CONTEXTO, aplicar_fusao_evento
from app.services.detection_events import publicar_evento, refrescar_evento_no_ponto, registrar_deteccao
from app.services.inmet_alert_source import obter_aviso_ativo
from app.services.weather_source import obter_condicoes_atuais
from data_fusion.historico_alagamento import indice_historico
from ml.detector import detectar_incidentes_imagem

logger = logging.getLogger(__name__)

_threads: list[threading.Thread] = []
_stop_event = threading.Event()


def _processar_frame(conteudo: bytes, latitude: float, longitude: float, threshold: float, cooldown: dict[str, float], nome_camera: str) -> None:
    caminho = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as arquivo:
            arquivo.write(conteudo)
            caminho = arquivo.name
        deteccoes = detectar_incidentes_imagem(caminho, threshold)
    except RuntimeError as exc:
        logger.warning("Detecção contínua de alagamento indisponível: %s", exc)
        return
    finally:
        if caminho:
            Path(caminho).unlink(missing_ok=True)

    alagamento = next((item for item in deteccoes if item.nome == "alagamento"), None)
    if alagamento is None:
        return

    agora = time.monotonic()
    ultimo = cooldown.get("alagamento", -10_000)
    if agora - ultimo < settings.gx_alerta_cooldown_seconds:
        return
    cooldown["alagamento"] = agora

    with SessionLocal() as db:
        if refrescar_evento_no_ponto(
            db, tipo="alagamento", latitude=latitude, longitude=longitude,
            dentro_de_segundos=settings.gx_alerta_cooldown_seconds,
        ):
            logger.info("Alagamento em %s renovado (evento ainda vivo no ponto)", nome_camera)
            return
        try:
            evento = registrar_deteccao(
                db,
                alagamento,
                conteudo,
                latitude,
                longitude,
                fonte_nome=f"MotSP YOLO Contínuo (alagamento) - {nome_camera}",
                fonte_descricao=f"Modelo dedicado de incidentes rodando direto na câmera pública CET-SP '{nome_camera}', sem confirmação humana.",
                modelo_ia="YOLO11 (modelo de incidentes GX)",
                origem="camera_continua_alagamento",
            )
            condicoes = obter_condicoes_atuais(latitude, longitude)
            if condicoes.get("disponivel") and condicoes.get("chuva_mm") is not None:
                db.add(DadoContextual(
                    evento_id=evento.id,
                    categoria=CATEGORIA_CONTEXTO,
                    chave="precipitacao_mm_h",
                    valor_numerico=float(condicoes["chuva_mm"]),
                    unidade="mm/h",
                ))

            aviso = obter_aviso_ativo()
            if aviso.get("disponivel") and aviso.get("menciona_alagamento"):
                db.add(DadoContextual(
                    evento_id=evento.id,
                    categoria=CATEGORIA_CONTEXTO,
                    chave="alerta_inmet_severidade",
                    valor_numerico=float(aviso["severidade_indice"]),
                    unidade="indice_0_10",
                ))

            # O histórico é gravado mesmo quando é zero, para separar uma via
            # que nunca alagou de uma via sem informação.
            indice_hist, descricao_hist = indice_historico(latitude, longitude)
            db.add(DadoContextual(
                evento_id=evento.id,
                categoria=CATEGORIA_CONTEXTO,
                chave="historico_alagamento_indice",
                valor_numerico=indice_hist,
                unidade="indice_0_10",
            ))

            db.commit()
            aplicar_fusao_evento(db, evento.id, persistir=True)
            publicar_evento(db, evento.id)
            logger.info(
                "Alagamento sinalizado em %s (confiança %.0f%%), histórico da via: %s",
                nome_camera, alagamento.confianca * 100, descricao_hist,
            )
        except Exception:
            logger.exception("Falha ao registrar evento de alagamento")


def _loop(snapshot_url: str, latitude: float, longitude: float, interval: float, threshold: float, nome_camera: str) -> None:
    import httpx

    cooldown: dict[str, float] = {}
    ultimo_hash: str | None = None
    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (MotSP flood-detection)"}) as client:
        while not _stop_event.is_set():
            try:
                response = client.get(snapshot_url)
                response.raise_for_status()
                conteudo = response.content
            except httpx.HTTPError as exc:
                logger.warning("Falha ao baixar snapshot de %s (%s): %s", nome_camera, snapshot_url, exc)
                _stop_event.wait(interval)
                continue

            if cet_camera_catalog.frame_esta_desatualizado(response.headers, settings.gx_camera_frescor_maximo_segundos):
                logger.warning(
                    "Câmera %s travada num frame antigo (Last-Modified: %s), frame ignorado",
                    nome_camera, response.headers.get("last-modified"),
                )
                _stop_event.wait(interval)
                continue

            hash_atual = hashlib.sha256(conteudo).hexdigest()
            if hash_atual != ultimo_hash:
                ultimo_hash = hash_atual
                _processar_frame(conteudo, latitude, longitude, threshold, cooldown, nome_camera)

            _stop_event.wait(interval)


def iniciar() -> None:
    """Começa a procurar alagamento em cada câmera, uma thread para cada."""
    global _threads
    if not settings.gx_alagamento_monitorar_catalogo:
        return

    _stop_event.clear()
    _threads = []
    for camera in cet_camera_catalog.CAMERAS:
        thread = threading.Thread(
            target=_loop,
            args=(
                camera.snapshot_url,
                camera.latitude,
                camera.longitude,
                settings.gx_live_detection_interval_seconds,
                settings.gx_yolo_incident_conf,
                camera.nome,
            ),
            daemon=True,
            name=f"gx-flood-detection-{camera.nome}",
        )
        thread.start()
        _threads.append(thread)
    logger.info("Detecção contínua de alagamento iniciada para %s câmera(s) (intervalo %ss)", len(cet_camera_catalog.CAMERAS), settings.gx_live_detection_interval_seconds)


def parar() -> None:
    _stop_event.set()
    for thread in _threads:
        thread.join(timeout=5)
