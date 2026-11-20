"""Ciclo de monitoramento das câmeras da CET-SP.

O monitoramento tem dois ritmos:

    quando o sistema liga, uma passada completa olha todas as câmeras e põe no
        mapa o que encontrar
    a partir do fim dessa passada, a cada 10 min (o ciclo geral) o sistema
        olha de novo as câmeras que têm evento no mapa
    as câmeras sem evento são olhadas a cada 60 s. Se aparecer um evento,
        a câmera passa a ser olhada no ciclo geral

Em cada câmera olhada, para cada tipo de evento, acontece uma destas coisas:

    viu o evento e ainda não existe evento no ponto: cria o evento
    viu o evento e já existe evento no ponto: atualiza o mesmo evento, com foto
        nova, dados de contexto novos e a fusão recalculada
    não viu e existe evento no ponto: conta um ciclo sem confirmação. No
        segundo ciclo seguido sem confirmação o evento é apagado, e a câmera
        volta para o ritmo de 60 s
    a câmera não mandou imagem nova: nada muda, porque não dá para saber se o
        evento continua

Como o evento é atualizado no lugar, o mapa nunca mostra dois eventos do mesmo
tipo na mesma câmera.

Só roda uma passada por vez. Na nuvem a CPU só existe enquanto alguém está com
o painel aberto, então o monitoramento para quando todos fecham o painel e
volta a frio quando alguém entra.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.evento import Evento
from app.models.log_sistema import LogSistema
from app.services import cet_camera_catalog, flood_detection, live_detection
from app.services.detection_events import Analise, atualizar_evento, buscar_evento_no_ponto, criar_evento
from app.services.event_retention import colapsar_eventos_duplicados, remover_eventos

logger = logging.getLogger(__name__)

Analisador = Callable[[bytes, float, float, str], Analise | None]

# completo: todas as câmeras. com_evento: o ciclo geral de 10 min.
# sem_evento: a verificação de 60 s.
Modo = Literal["completo", "com_evento", "sem_evento"]
MODOS: tuple[Modo, ...] = ("completo", "com_evento", "sem_evento")


@dataclass(frozen=True)
class CameraMonitorada:
    snapshot_url: str
    latitude: float
    longitude: float
    nome: str
    transito: bool
    alagamento: bool


_ciclo_lock = threading.Lock()
# Quantos ciclos seguidos cada evento passou sem ser visto de novo.
_ciclos_sem_confirmacao: dict[int, int] = {}
# Hash da última imagem de cada câmera, para perceber câmera travada.
_ultimo_hash: dict[str, str] = {}
# Resumo da última passada de cada modo.
_ultimos_resumos: dict[str, dict] = {}

_parar = threading.Event()
_thread: threading.Thread | None = None


def cameras_monitoradas() -> list[CameraMonitorada]:
    """Lista as câmeras e o que procurar em cada uma, conforme a configuração."""
    cameras: list[CameraMonitorada] = []

    snapshot_url = settings.gx_camera_snapshot_url
    if snapshot_url:
        if settings.gx_camera_latitude is None or settings.gx_camera_longitude is None:
            logger.warning("GX_CAMERA_SNAPSHOT_URL definida sem GX_CAMERA_LATITUDE/GX_CAMERA_LONGITUDE; câmera avulsa ignorada")
        else:
            cameras.append(CameraMonitorada(
                snapshot_url, settings.gx_camera_latitude, settings.gx_camera_longitude,
                "câmera personalizada", transito=True, alagamento=False,
            ))

    transito = settings.gx_transito_monitorar_catalogo
    alagamento = settings.gx_alagamento_monitorar_catalogo
    if transito or alagamento:
        cameras.extend(
            CameraMonitorada(cam.snapshot_url, cam.latitude, cam.longitude, cam.nome, transito, alagamento)
            for cam in cet_camera_catalog.CAMERAS
        )
    return cameras


def _analisadores(camera: CameraMonitorada) -> list[tuple[str, Analisador]]:
    analisadores: list[tuple[str, Analisador]] = []
    if camera.transito:
        analisadores.append((live_detection.TIPO, live_detection.analisar_frame))
    if camera.alagamento:
        analisadores.append((flood_detection.TIPO, flood_detection.analisar_frame))
    return analisadores


def _analisadores_do_modo(db, camera: CameraMonitorada, modo: Modo) -> list[tuple[str, Analisador]]:
    """Escolhe os tipos que esta passada olha na câmera.

    Cada tipo segue o seu ritmo. Uma câmera com evento de trânsito e sem evento
    de alagamento tem o trânsito olhado no ciclo geral e o alagamento a cada 60 s.
    """
    analisadores = _analisadores(camera)
    if modo == "completo":
        return analisadores
    escolhidos = []
    for tipo, analisar in analisadores:
        tem_evento = buscar_evento_no_ponto(db, tipo=tipo, latitude=camera.latitude, longitude=camera.longitude) is not None
        if tem_evento == (modo == "com_evento"):
            escolhidos.append((tipo, analisar))
    return escolhidos


def _baixar_imagem(client: httpx.Client, camera: CameraMonitorada) -> bytes | None:
    """Baixa a imagem da câmera. Devolve None se não houver imagem nova."""
    try:
        response = client.get(camera.snapshot_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Falha ao baixar a imagem de %s (%s): %s", camera.nome, camera.snapshot_url, exc)
        return None

    if cet_camera_catalog.frame_esta_desatualizado(response.headers, settings.gx_camera_frescor_maximo_segundos):
        logger.warning(
            "Câmera %s travada num frame antigo (Last-Modified: %s), frame ignorado",
            camera.nome, response.headers.get("last-modified"),
        )
        return None

    conteudo = response.content
    hash_atual = hashlib.sha256(conteudo).hexdigest()
    if _ultimo_hash.get(camera.snapshot_url) == hash_atual:
        logger.info("Câmera %s mandou a mesma imagem da última vez, frame ignorado", camera.nome)
        return None
    _ultimo_hash[camera.snapshot_url] = hash_atual
    return conteudo


def _aplicar_resultado(
    db,
    camera: CameraMonitorada,
    tipo: str,
    analise: Analise | None,
    conteudo: bytes,
    resumo: dict,
) -> None:
    """Cria, atualiza ou apaga o evento da câmera conforme o que foi visto."""
    existente = buscar_evento_no_ponto(db, tipo=tipo, latitude=camera.latitude, longitude=camera.longitude)

    if analise is not None:
        if existente is not None:
            status_antes = existente.status
            evento = atualizar_evento(db, existente, analise, conteudo, endereco=camera.nome)
            _ciclos_sem_confirmacao.pop(evento.id, None)
            resumo["atualizados"] += 1
            logger.info(
                "Evento #%s (%s) em %s confirmado de novo: %s -> %s",
                evento.id, tipo, camera.nome, status_antes, evento.status,
            )
        else:
            evento = criar_evento(db, analise, conteudo, camera.latitude, camera.longitude, endereco=camera.nome)
            # O SQLite pode reaproveitar o número de um evento apagado. O evento
            # novo não pode herdar a contagem do antigo.
            _ciclos_sem_confirmacao.pop(evento.id, None)
            resumo["criados"] += 1
            logger.info("Evento #%s (%s) criado em %s: %s", evento.id, tipo, camera.nome, evento.status)
        return

    if existente is None:
        return

    faltas = _ciclos_sem_confirmacao.get(existente.id, 0) + 1
    if faltas >= settings.gx_ciclos_sem_confirmacao_para_remover:
        _ciclos_sem_confirmacao.pop(existente.id, None)
        evento_id = existente.id
        remover_eventos(db, [evento_id])
        resumo["removidos"] += 1
        logger.info("Evento #%s (%s) em %s removido: %s ciclos sem confirmação", evento_id, tipo, camera.nome, faltas)
    else:
        _ciclos_sem_confirmacao[existente.id] = faltas
        resumo["sem_confirmacao"] += 1
        logger.info("Evento #%s (%s) em %s não foi visto neste ciclo (%s de %s)",
                    existente.id, tipo, camera.nome, faltas, settings.gx_ciclos_sem_confirmacao_para_remover)


def _rodar(cameras: list[CameraMonitorada], modo: Modo) -> dict:
    inicio = time.monotonic()
    resumo = {
        "executado": True,
        "modo": modo,
        "cameras": 0,
        "sem_imagem": 0,
        "criados": 0,
        "atualizados": 0,
        "sem_confirmacao": 0,
        "removidos": 0,
        "falhas": 0,
    }
    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (MotSP monitoramento)"}) as client, SessionLocal() as db:
        for camera in cameras:
            analisadores = _analisadores_do_modo(db, camera, modo)
            if not analisadores:
                continue
            resumo["cameras"] += 1
            conteudo = _baixar_imagem(client, camera)
            if conteudo is None:
                resumo["sem_imagem"] += 1
                continue
            for tipo, analisar in analisadores:
                try:
                    analise = analisar(conteudo, camera.latitude, camera.longitude, camera.nome)
                    _aplicar_resultado(db, camera, tipo, analise, conteudo, resumo)
                except Exception:
                    # Uma falha numa câmera não pode parar as outras. O evento
                    # que já existe fica como está.
                    db.rollback()
                    resumo["falhas"] += 1
                    logger.exception("Falha ao analisar %s em %s", tipo, camera.nome)

        colapsar_eventos_duplicados(db)

        # Esquece a contagem dos eventos que já saíram do banco.
        abertos = {i for (i,) in db.query(Evento.id)}
        for evento_id in list(_ciclos_sem_confirmacao):
            if evento_id not in abertos:
                del _ciclos_sem_confirmacao[evento_id]

        resumo["duracao_segundos"] = round(time.monotonic() - inicio, 1)
        resumo["terminado_em"] = datetime.now(UTC).isoformat(timespec="seconds")
        # A verificação de 60 s só vai para o log quando algo acontece, para
        # não encher a tabela com uma linha por minuto.
        if modo != "sem_evento" or resumo["criados"] or resumo["falhas"]:
            db.add(LogSistema(
                nivel="INFO",
                modulo="ciclo_monitoramento",
                mensagem=(
                    f"Passada {modo} em {resumo['duracao_segundos']} s: {resumo['cameras']} câmeras, "
                    f"{resumo['criados']} criados, {resumo['atualizados']} atualizados, "
                    f"{resumo['removidos']} removidos"
                ),
                contexto=resumo,
            ))
            db.commit()
    return resumo


def executar_ciclo(modo: Modo = "completo") -> dict:
    """Roda uma passada pelas câmeras e devolve o resumo do que aconteceu."""
    if not _ciclo_lock.acquire(blocking=False):
        return {"executado": False, "motivo": "outro ciclo ainda está rodando"}
    try:
        cameras = cameras_monitoradas()
        if not cameras:
            return {"executado": False, "motivo": "nenhuma câmera configurada"}
        resumo = _rodar(cameras, modo)
        _ultimos_resumos[modo] = resumo
        if modo != "sem_evento" or resumo["criados"]:
            logger.info("Passada %s concluída: %s", modo, resumo)
        return resumo
    finally:
        _ciclo_lock.release()


def ultimos_resumos() -> dict[str, dict | None]:
    return {modo: _ultimos_resumos.get(modo) for modo in MODOS}


def _executar_com_seguranca(modo: Modo) -> None:
    try:
        executar_ciclo(modo)
    except Exception:
        logger.exception("Passada %s do monitoramento falhou", modo)


def _loop_interno() -> None:
    periodo_geral = settings.gx_ciclo_minutos * 60
    periodo_sem_evento = settings.gx_ciclo_sem_evento_segundos

    _executar_com_seguranca("completo")
    # Os 10 min do ciclo geral começam a contar no fim da passada completa.
    proximo_geral = time.monotonic() + periodo_geral
    proximo_sem_evento = time.monotonic() + periodo_sem_evento

    while True:
        espera = min(proximo_geral, proximo_sem_evento) - time.monotonic()
        if _parar.wait(max(0.0, espera)):
            return
        if time.monotonic() >= proximo_geral:
            _executar_com_seguranca("com_evento")
            # Mantém o ciclo geral no mesmo compasso. Se uma passada atrasar
            # muito, pula para o próximo horário em vez de rodar várias seguidas.
            while proximo_geral <= time.monotonic():
                proximo_geral += periodo_geral
        if time.monotonic() >= proximo_sem_evento:
            _executar_com_seguranca("sem_evento")
            # Os 60 s contam a partir do fim da verificação anterior.
            proximo_sem_evento = time.monotonic() + periodo_sem_evento


def iniciar() -> None:
    """Liga o monitoramento: uma passada completa agora e depois os dois ritmos."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_loop_interno, daemon=True, name="gx-ciclo-monitoramento")
    _thread.start()
    logger.info(
        "Monitoramento ligado: câmeras com evento a cada %s min, sem evento a cada %s s",
        settings.gx_ciclo_minutos, settings.gx_ciclo_sem_evento_segundos,
    )


def parar() -> None:
    global _thread
    _parar.set()
    if _thread is not None:
        _thread.join(timeout=5)
        _thread = None
