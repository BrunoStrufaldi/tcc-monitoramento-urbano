"""Detecção contínua a partir de uma câmera pública CET-SP, sem operador no loop.

A CET-SP não expõe RTSP: cada câmera é uma imagem JPEG estática num endpoint
por ID (ex.: ``https://cameras.cetsp.com.br/Cams/225/1.jpg``), atualizada
periodicamente pelo próprio servidor deles. Por isso o loop aqui é HTTP GET
em intervalo, não captura de vídeo.

Nem sempre esse "atualizada periodicamente" é verdade: descoberto na prática
(26/08/2026) que uma câmera específica travou servindo sempre o mesmo JPEG de
meses atrás (200 OK, bytes válidos, só o conteúdo é velho) — sem checagem,
isso vira um evento de "trânsito agora" carimbado com o horário de execução
mas com uma foto de outra hora do dia. Por isso todo frame baixado passa por
``cet_camera_catalog.frame_esta_desatualizado`` (usa o cabeçalho HTTP
``Last-Modified``) antes de virar detecção; frame velho é descartado como se
fosse falha de rede.

O YOLO/COCO padrão só reconhece objetos (veículo, ônibus, caminhão, moto), não
"trânsito" como classe. Por isso não criamos mais um evento por veículo
avulso: contamos quantos veículos aparecem juntos no mesmo frame e, acima de
um limite, sinalizamos congestionamento — aí sim um evento único de
"trânsito". Mas a contagem sozinha erra para os dois lados: soma os dois
sentidos da via + a fila da transversal (avenida larga fluindo passa do limite
à toa) e subconta o JPEG noturno da câmera pública (via parada fica em 4..7
veículos). Por isso quem arbitra é a TomTom Traffic API
(``tomtom_traffic_source``, velocidade atual x livre do trecho, dado ao vivo —
ver o módulo pra entender por que Waze for Cities e o CGE não davam pra usar
aqui), em três faixas de contagem decididas por ``_avaliar_gatilho_transito``:
acima de ``gx_transito_min_veiculos_confirmado`` a contagem cria sozinha; entre
``gx_transito_min_veiculos`` e ``_confirmado`` a TomTom pode **vetar** (sem
``TOMTOM_API_KEY``, essa faixa volta a ser decidida só por contagem); e entre
``gx_transito_min_veiculos_corroborado`` e ``gx_transito_min_veiculos`` é a
TomTom que **cria** — sem ela essa faixa não gera nada. Criado o evento, os
dois índices entram na mesma dimensão de clima do ``data_fusion``.

Duas fontes de câmera, cada uma opt-in:
- ``GX_CAMERA_SNAPSHOT_URL`` (+ latitude/longitude): uma câmera avulsa
  qualquer, útil pra testar com uma URL controlada.
- ``GX_TRANSITO_MONITORAR_CATALOGO=true``: todas as câmeras públicas da CET-SP
  em ``cet_camera_catalog`` (várias avenidas de verdade, não uma só).
Cada câmera roda em thread própria, com cooldown independente, pra não deixar
uma avenida congestionada silenciar o alerta de outra.

Ativar qualquer uma dessas fontes é uma decisão explícita de quem opera o
backend, ciente de que aqui não há a confirmação humana por evento que o
resto do sistema exige. Eventos são publicados no loop assíncrono principal
via ``app.broadcast.schedule_coroutine``.
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
from app.services.data_fusion_service import aplicar_fusao_evento
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
    """Reduz N detecções de veículos a uma única detecção sintética de trânsito.

    A confiança do evento sintético é a média das ``limite`` detecções de maior
    confiança, não de todas: num frame de câmera de trânsito os veículos ao
    fundo aparecem pequenos e com score naturalmente baixo, e a média de todos
    derrubava a dimensão de IA da fusão mesmo com congestionamento óbvio no
    primeiro plano. O que importa aqui é "há N veículos bem detectados juntos",
    não a qualidade média de cada lata distante. Na faixa corroborada pela
    TomTom há menos de ``limite`` veículos no quadro e a média cai sobre todos
    eles — é o melhor que o frame oferece.
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
        # Evento.tipo precisa ser o nome específico ("transito"), não a
        # categoria ampla de CLASSES_URBANAS ("mobilidade") — é o que
        # data_fusion.scores usa para escolher o cálculo de clima certo.
        tipo="transito",
        bbox=(min(xs1), min(ys1), max(xs2), max(ys2)),
    )


def _avaliar_gatilho_transito(n_veiculos: int, fluxo_tomtom: dict) -> tuple[bool, str]:
    """Decide se a contagem de veículos deve virar um evento de trânsito.

    Três faixas de contagem, da mais alta para a mais baixa:

    - ``>= gx_transito_min_veiculos_confirmado``: frame muito cheio é sinal
      forte por si só; cria sem consultar ninguém.
    - ``gx_transito_min_veiculos .. _confirmado``: a contagem sozinha soma os
      dois sentidos da via + a fila da transversal + carro parado, e numa
      avenida larga passa do limite mesmo com tudo fluindo — a TomTom **veta**
      se medir o trecho em velocidade de fluxo livre. Sem TomTom, a decisão
      volta a ser só por contagem (comportamento antigo).
    - ``gx_transito_min_veiculos_corroborado .. gx_transito_min_veiculos``: a
      contagem é baixa demais para criar sozinha, e aqui a TomTom **cria** — é
      ela quem sustenta o evento. Caso que motivou a faixa (04/09/2026, rush
      das 19h): o JPEG noturno da câmera pública derruba o score do YOLO, a
      contagem fica em 4..7 e o portão de contagem barrava o frame *antes* de
      perguntar à TomTom, que estava reportando 9 km/h numa via de 20 km/h
      livres. A fonte que sabia da lentidão nunca era ouvida. Sem TomTom
      disponível esta faixa não cria nada: não há o que corroborar.

    Retorna ``(criar, motivo)``.
    """
    if n_veiculos >= settings.gx_transito_min_veiculos_confirmado:
        return True, f"contagem alta ({n_veiculos} veículos)"
    if fluxo_tomtom.get("via_fechada"):
        return True, "TomTom reporta via fechada"

    # Abaixo do mínimo a contagem não se sustenta sozinha: a TomTom deixa de
    # ser desempate e passa a ser a fonte que cria (ou não) o evento.
    corroboracao_obrigatoria = n_veiculos < settings.gx_transito_min_veiculos

    indice = fluxo_tomtom.get("indice_congestionamento")
    if not fluxo_tomtom.get("disponivel") or indice is None:
        if corroboracao_obrigatoria:
            return False, f"sem TomTom e contagem baixa ({n_veiculos} veículos) — nada a corroborar"
        return True, "sem TomTom — decisão só por contagem"

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
    # O portão aqui é o PISO, não o mínimo: entre o piso e o mínimo quem decide
    # é a TomTom (ver _avaliar_gatilho_transito). Antes o mínimo barrava o frame
    # antes da consulta e a TomTom nunca era ouvida na faixa baixa.
    if len(veiculos) < settings.gx_transito_min_veiculos_corroborado:
        return

    agora = time.monotonic()
    if agora - cooldown.get("transito", -10_000) < settings.gx_alerta_cooldown_seconds:
        return
    # Cooldown curto e separado: limita a taxa de consulta à TomTom sem calar a
    # câmera por meia hora quando o veto foi dela, não nosso.
    if agora - cooldown.get("transito_veto", -10_000) < settings.gx_transito_veto_cooldown_seconds:
        return

    transito = _detectar_congestionamento(veiculos, limite)
    indice = round(min(10.0, len(veiculos) / 2), 1)

    with SessionLocal() as db:
        # Congestionamento ainda ativo no mesmo ponto → renova a marcação
        # existente em vez de criar outra (o cooldown em memória se perde a
        # cada restart; a checagem no banco não). Evento já vivo não gasta
        # chamada da TomTom nem passa pela decisão de gatilho de novo.
        if refrescar_evento_no_ponto(
            db, tipo="transito", latitude=latitude, longitude=longitude,
            dentro_de_segundos=settings.gx_alerta_cooldown_seconds,
        ):
            cooldown["transito"] = agora
            logger.info("Trânsito em %s renovado (evento ainda vivo no ponto)", nome_camera)
            return

        # A TomTom entra ANTES da criação: na faixa gx_transito_min_veiculos ..
        # gx_transito_min_veiculos_confirmado ela pode vetar um "congestionamento"
        # que é só contagem dos dois sentidos numa avenida larga fluindo.
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
                categoria="clima",
                chave="indice_congestionamento",
                valor_numerico=indice,
                unidade="indice_0_10",
            ))
            if fluxo_tomtom.get("disponivel"):
                db.add(DadoContextual(
                    evento_id=evento.id,
                    categoria="clima",
                    chave="indice_congestionamento_tomtom",
                    valor_numerico=fluxo_tomtom["indice_congestionamento"],
                    unidade="indice_0_10",
                ))
            db.commit()
            aplicar_fusao_evento(db, evento.id, persistir=True)
            publicar_evento(db, evento.id)
            logger.info(
                "Trânsito sinalizado em %s: %s veículos no quadro (índice %.1f) — %s",
                nome_camera, len(veiculos), indice, motivo,
            )
        except Exception:
            logger.exception("Falha ao registrar evento de trânsito")


def _loop(snapshot_url: str, latitude: float, longitude: float, interval: float, threshold: float, nome_camera: str) -> None:
    import httpx

    cooldown: dict[str, float] = {}
    ultimo_hash: str | None = None
    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (GX-TCC live-detection)"}) as client:
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


def _fontes_camera() -> list[tuple[str, float, float, str]]:
    """Resolve as câmeras a monitorar: (snapshot_url, latitude, longitude, nome)."""
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
    """Sobe uma thread de detecção contínua por câmera configurada, se houver alguma."""
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
