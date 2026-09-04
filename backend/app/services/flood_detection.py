"""Detecção contínua de alagamento nas câmeras públicas CET-SP, sem operador
no loop e sem depender de dataset em lote.

Antes disso, a única detecção de alagamento era reativa: rodava só quando o
GeoSampa (``context_monitor.py``, removido) notava um registro da Defesa
Civil — que podia ter semanas ou meses de defasagem entre o ocorrido e a
publicação. Decisão do grupo foi manter só dado em tempo real; sem GeoSampa,
a única forma de continuar detectando alagamento de forma autônoma é rodar o
modelo dedicado de incidentes direto nas câmeras, do mesmo jeito que
``live_detection.py`` já faz pra trânsito (mesmo catálogo de 10 câmeras,
mesma checagem de frescor de frame via
``cet_camera_catalog.frame_esta_desatualizado`` — sem ela um evento "ao
vivo" podia sair de uma foto de meses atrás, foi exatamente o bug achado na
câmera 22 "Paulista - Metrô Consolação").

Exige ``GX_YOLO_INCIDENT_MODEL`` configurado (o peso COCO padrão não tem
classe de alagamento — ver ``ml/detector.py``). Sem o modelo dedicado, o loop
sobe mas cada frame é descartado silenciosamente (mesmo comportamento
defensivo do resto do sistema quando falta peso treinado).

Ativado por ``GX_ALAGAMENTO_MONITORAR_CATALOGO=true``, opt-in — decisão
explícita de quem opera o backend, ciente de que aqui não há confirmação
humana por evento. Eventos são publicados no loop assíncrono principal via
``app.broadcast.schedule_coroutine``.

Cada detecção também busca duas fontes climáticas independentes e grava como
dado contextual: a chuva atual no ponto exato (Open-Meteo, via
``weather_source`` — sensor bruto, dado ao vivo) e um aviso oficial ativo do
INMET pra São Paulo (``inmet_alert_source`` — julgamento institucional, só
gravado quando o aviso menciona risco de alagamento). Mesmo padrão do
trânsito (índice de veículos + TomTom): quando as duas existem,
``data_fusion.scores`` faz a média em vez de confiar só numa.

Grava ainda um terceiro insumo, agora estático: o histórico de alagamento da
via (``data_fusion.historico_alagamento``, lookup local sem rede). É prior
espacial, não gatilho nem fonte ao vivo — reforça a confiabilidade quando já
há chuva/aviso e a derruba quando não há sinal algum numa via que nunca
alagou (falso positivo provável do modelo de incidentes).
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.dado_contextual import DadoContextual
from app.services import cet_camera_catalog
from app.services.data_fusion_service import aplicar_fusao_evento
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

    bruto = next((item for item in deteccoes if item.nome == "alagamento"), None)
    if bruto is None:
        return

    agora = time.monotonic()
    ultimo = cooldown.get("alagamento", -10_000)
    if agora - ultimo < settings.gx_alerta_cooldown_seconds:
        return
    cooldown["alagamento"] = agora

    # CLASSES_URBANAS guarda a categoria ampla em Deteccao.tipo ("clima"),
    # não o nome específico — registrar_deteccao usa tipo direto como
    # Evento.tipo, então precisa virar "alagamento" (mesmo ajuste que
    # live_detection.py faz pra "transito" não virar "mobilidade").
    alagamento = replace(bruto, tipo="alagamento")

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
                    categoria="clima",
                    chave="precipitacao_mm_h",
                    valor_numerico=float(condicoes["chuva_mm"]),
                    unidade="mm/h",
                ))

            aviso = obter_aviso_ativo()
            if aviso.get("disponivel") and aviso.get("menciona_alagamento"):
                db.add(DadoContextual(
                    evento_id=evento.id,
                    categoria="clima",
                    chave="alerta_inmet_severidade",
                    valor_numerico=float(aviso["severidade_indice"]),
                    unidade="indice_0_10",
                ))

            # Prior espacial estático (lookup local, sem rede): histórico de
            # alagamento da via. Gravado sempre — inclusive 0.0 — para o Data
            # Fusion distinguir "via sem histórico" de "sem informação".
            indice_hist, descricao_hist = indice_historico(latitude, longitude)
            db.add(DadoContextual(
                evento_id=evento.id,
                categoria="clima",
                chave="historico_alagamento_indice",
                valor_numerico=indice_hist,
                unidade="indice_0_10",
            ))

            db.commit()
            aplicar_fusao_evento(db, evento.id, persistir=True)
            publicar_evento(db, evento.id)
            logger.info(
                "Alagamento sinalizado em %s (confiança %.0f%%) — histórico da via: %s",
                nome_camera, alagamento.confianca * 100, descricao_hist,
            )
        except Exception:
            logger.exception("Falha ao registrar evento de alagamento")


def _loop(snapshot_url: str, latitude: float, longitude: float, interval: float, threshold: float, nome_camera: str) -> None:
    import httpx

    cooldown: dict[str, float] = {}
    ultimo_hash: str | None = None
    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (GX-TCC flood-detection)"}) as client:
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
                    "Câmera %s travada num frame antigo (Last-Modified: %s) — ignorando, não é tempo real",
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
    """Sobe uma thread de detecção de alagamento por câmera do catálogo, se ativado."""
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
