"""Monitora as câmeras da CET-SP e detecta trânsito parado.

De tempos em tempos a imagem de cada câmera é baixada e o YOLO conta quantos
veículos aparecem nela. Se forem muitos, vira um evento de trânsito. Se forem
poucos, a TomTom ajuda a decidir se a via está mesmo lenta. Imagens antigas,
de câmera travada, são ignoradas.
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
from app.services.detection_events import publicar_evento, refrescar_evento_no_ponto, registrar_deteccao
from app.services.data_fusion_service import CATEGORIA_CONTEXTO, aplicar_fusao_evento
from app.services.tomtom_traffic_source import obter_fluxo_transito
from ml.detector import CLASSES_URBANAS, Deteccao, detectar_imagem_real

logger = logging.getLogger(__name__)

_threads: list[threading.Thread] = []
_stop_event = threading.Event()

_CLASSES_VEICULO = {"veiculo", "motocicleta", "onibus", "caminhao"}
_TRANSITO_ID, _TRANSITO_META = next(
    (classe_id, meta) for classe_id, meta in CLASSES_URBANAS.items() if meta["nome"] == "transito"
)


def _detectar_congestionamento(veiculos: list[Deteccao], limite: int) -> Deteccao:
    """Junta os veículos detectados em um único evento de trânsito.

    A confiança usa só os veículos mais bem detectados, porque os carros ao
    fundo da imagem costumam ter nota baixa.
    """
    melhores = sorted((d.confianca for d in veiculos), reverse=True)[:limite]
    confianca = round(sum(melhores) / len(melhores), 3)
    xs1 = [d.bbox[0] for d in veiculos]
    ys1 = [d.bbox[1] for d in veiculos]
    xs2 = [d.bbox[2] for d in veiculos]
    ys2 = [d.bbox[3] for d in veiculos]
    return Deteccao(
        classe_id=_TRANSITO_ID,
        nome="transito",
        confianca=confianca,
        severidade=_TRANSITO_META["severidade"],
        tipo=_TRANSITO_META["tipo"],
        bbox=(min(xs1), min(ys1), max(xs2), max(ys2)),
    )


def _avaliar_gatilho_transito(n_veiculos: int, fluxo_tomtom: dict) -> tuple[bool, str]:
    """Decide se a quantidade de veículos vira um evento de trânsito.

    Com muitos veículos, cria direto. Com uma quantidade média, cria, a não ser
    que a TomTom diga que a via está fluindo. Com poucos veículos, só cria se a
    TomTom confirmar a lentidão. Devolve a decisão e o motivo.
    """
    if n_veiculos >= settings.gx_transito_min_veiculos_confirmado:
        return True, f"contagem alta ({n_veiculos} veículos)"
    if fluxo_tomtom.get("via_fechada"):
        return True, "TomTom reporta via fechada"

    corroboracao_obrigatoria = n_veiculos < settings.gx_transito_min_veiculos

    indice = fluxo_tomtom.get("indice_congestionamento")
    if not fluxo_tomtom.get("disponivel") or indice is None:
        if corroboracao_obrigatoria:
            return False, f"sem TomTom e contagem baixa ({n_veiculos} veículos), nada a corroborar"
        return True, "sem TomTom, decisão só por contagem"

    if indice >= settings.gx_transito_tomtom_indice_minimo:
        if corroboracao_obrigatoria:
            return True, f"TomTom sustenta a contagem baixa (índice {indice:.1f}/10)"
        return True, f"TomTom confirma lentidão (índice {indice:.1f}/10)"
    return False, f"TomTom indica trecho fluindo (índice {indice:.1f}/10)"


def _processar_frame(conteudo: bytes, latitude: float, longitude: float, threshold: float, cooldown: dict[str, float], nome_camera: str = "câmera personalizada") -> None:
    caminho = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as arquivo:
            arquivo.write(conteudo)
            caminho = arquivo.name
        deteccoes = detectar_imagem_real(caminho, threshold)
    except RuntimeError as exc:
        logger.warning("Detecção contínua indisponível: %s", exc)
        return
    finally:
        if caminho:
            Path(caminho).unlink(missing_ok=True)

    veiculos = [item for item in deteccoes if item.nome in _CLASSES_VEICULO]
    limite = settings.gx_transito_min_veiculos
    # Com tão poucos veículos nem vale consultar a TomTom.
    if len(veiculos) < settings.gx_transito_min_veiculos_corroborado:
        return

    agora = time.monotonic()
    if agora - cooldown.get("transito", -10_000) < settings.gx_alerta_cooldown_seconds:
        return
    # Se a TomTom recusou há pouco, espera um tempo antes de perguntar de novo.
    if agora - cooldown.get("transito_veto", -10_000) < settings.gx_transito_veto_cooldown_seconds:
        return

    transito = _detectar_congestionamento(veiculos, limite)
    indice = round(min(10.0, len(veiculos) / 2), 1)

    with SessionLocal() as db:
        # Se já tem um evento ativo nesse ponto, só atualiza ele em vez de criar outro.
        if refrescar_evento_no_ponto(
            db, tipo="transito", latitude=latitude, longitude=longitude,
            dentro_de_segundos=settings.gx_alerta_cooldown_seconds,
        ):
            cooldown["transito"] = agora
            logger.info("Trânsito em %s renovado (evento ainda vivo no ponto)", nome_camera)
            return

        cooldown["transito_veto"] = agora
        fluxo_tomtom = obter_fluxo_transito(latitude, longitude)
        criar, motivo = _avaliar_gatilho_transito(len(veiculos), fluxo_tomtom)
        if not criar:
            logger.info("Trânsito descartado em %s: %s (%s veículos no quadro)", nome_camera, motivo, len(veiculos))
            return
        cooldown["transito"] = agora

        try:
            evento = registrar_deteccao(
                db,
                transito,
                conteudo,
                latitude,
                longitude,
                fonte_nome=f"MotSP YOLO Contínuo - {nome_camera}",
                fonte_descricao=f"Contagem de veículos pela câmera pública CET-SP '{nome_camera}', sem confirmação humana.",
                modelo_ia="YOLO11 (contagem de veículos)",
                origem="camera_continua_contagem",
                deteccoes_para_anotar=veiculos,
            )
            db.add(DadoContextual(
                evento_id=evento.id,
                categoria=CATEGORIA_CONTEXTO,
                chave="indice_congestionamento",
                valor_numerico=indice,
                unidade="indice_0_10",
            ))
            if fluxo_tomtom.get("disponivel"):
                db.add(DadoContextual(
                    evento_id=evento.id,
                    categoria=CATEGORIA_CONTEXTO,
                    chave="indice_congestionamento_tomtom",
                    valor_numerico=fluxo_tomtom["indice_congestionamento"],
                    unidade="indice_0_10",
                ))
            db.commit()
            aplicar_fusao_evento(db, evento.id, persistir=True)
            publicar_evento(db, evento.id)
            logger.info(
                "Trânsito sinalizado em %s: %s veículos no quadro (índice %.1f), %s",
                nome_camera, len(veiculos), indice, motivo,
            )
        except Exception:
            logger.exception("Falha ao registrar evento de trânsito")


def _loop(snapshot_url: str, latitude: float, longitude: float, interval: float, threshold: float, nome_camera: str) -> None:
    import httpx

    cooldown: dict[str, float] = {}
    ultimo_hash: str | None = None
    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (MotSP live-detection)"}) as client:
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


def _fontes_camera() -> list[tuple[str, float, float, str]]:
    """Lista as câmeras que vão ser monitoradas."""
    fontes: list[tuple[str, float, float, str]] = []

    snapshot_url = settings.gx_camera_snapshot_url
    if snapshot_url:
        if settings.gx_camera_latitude is None or settings.gx_camera_longitude is None:
            logger.warning("GX_CAMERA_SNAPSHOT_URL definida sem GX_CAMERA_LATITUDE/GX_CAMERA_LONGITUDE; câmera avulsa ignorada")
        else:
            fontes.append((snapshot_url, settings.gx_camera_latitude, settings.gx_camera_longitude, "câmera personalizada"))

    if settings.gx_transito_monitorar_catalogo:
        fontes.extend((cam.snapshot_url, cam.latitude, cam.longitude, cam.nome) for cam in cet_camera_catalog.CAMERAS)

    return fontes


def iniciar() -> None:
    """Começa a monitorar cada câmera configurada, uma thread para cada."""
    global _threads
    fontes = _fontes_camera()
    if not fontes:
        return

    _stop_event.clear()
    _threads = []
    for snapshot_url, latitude, longitude, nome_camera in fontes:
        thread = threading.Thread(
            target=_loop,
            args=(
                snapshot_url,
                latitude,
                longitude,
                settings.gx_live_detection_interval_seconds,
                settings.yolo_threshold,
                nome_camera,
            ),
            daemon=True,
            name=f"gx-live-detection-{nome_camera}",
        )
        thread.start()
        _threads.append(thread)
    logger.info("Detecção contínua iniciada para %s câmera(s) (intervalo %ss)", len(fontes), settings.gx_live_detection_interval_seconds)


def parar() -> None:
    _stop_event.set()
    for thread in _threads:
        thread.join(timeout=5)
