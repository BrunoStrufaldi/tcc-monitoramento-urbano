"""Mede a latência real de cada etapa do pipeline do MotSP.

Nada aqui é estimativa: roda os pesos do projeto (``ml/models``) sobre frames
reais das câmeras da CET-SP (``ml/datasets/holdout_0902``) e cronometra etapa
por etapa, do JPEG que chega até o evento aparecer no painel via WebSocket.

O banco e a pasta de evidências são redirecionados para um diretório
temporário — a medição não escreve no ``gx.db`` nem em
``backend/app/data/evidencias``.

Uso (a partir da raiz do projeto):
    backend\\venv\\Scripts\\python.exe backend\\benchmark_latencia.py
    ... --repeticoes 5             # nº de passadas sobre o conjunto de frames
    ... --json backend/data/latencia.json
    ... --cpu                      # inclui a comparação CPU x GPU (lento)
    ... --rede                     # baixa snapshot real da CET (usa internet)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import platform
import shutil
import statistics
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _caminho in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

# Precisa vir antes de importar app.config: o pydantic-settings lê o ambiente
# na instanciação, e variável de ambiente tem precedência sobre o .env.
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="motsp-latencia-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (_TEMP_DIR / "bench.db").as_posix()
os.environ["GX_MONITORAMENTO_ATIVO"] = "false"

import httpx  # noqa: E402
import websockets  # noqa: E402

from app.config import settings  # noqa: E402
from app.services import detection_events  # noqa: E402
from app.services.data_fusion_service import aplicar_fusao_evento  # noqa: E402
from app.services.detection_events import registrar_deteccao  # noqa: E402
from app.services.visual_validation import VisualValidationService  # noqa: E402
from ml import detector as ml_detector  # noqa: E402

# Evidências da medição vão para o diretório temporário, não para o projeto.
detection_events._EVIDENCIAS_DIR = _TEMP_DIR / "evidencias"

PORTA = 8931


# --------------------------------------------------------------------------- #
# Estatística
# --------------------------------------------------------------------------- #

def _percentil(ordenado: list[float], p: float) -> float:
    """Percentil por posto mais próximo — sem interpolação, amostra pequena."""
    if not ordenado:
        return float("nan")
    indice = max(0, math.ceil(p / 100 * len(ordenado)) - 1)
    return ordenado[min(indice, len(ordenado) - 1)]


def _resumir(etapa: str, amostras: list[float], nota: str = "") -> dict:
    ordenado = sorted(amostras)
    return {
        "etapa": etapa,
        "n": len(ordenado),
        "media": statistics.fmean(ordenado),
        "desvio": statistics.pstdev(ordenado) if len(ordenado) > 1 else 0.0,
        "p50": _percentil(ordenado, 50),
        "p95": _percentil(ordenado, 95),
        "min": ordenado[0],
        "max": ordenado[-1],
        "nota": nota,
    }


def _cronometrar(funcao, argumentos: list, repeticoes: int) -> list[float]:
    amostras: list[float] = []
    for _ in range(repeticoes):
        for argumento in argumentos:
            inicio = time.perf_counter()
            funcao(argumento)
            amostras.append((time.perf_counter() - inicio) * 1000)
    return amostras


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #

def _frames(limite: int | None) -> list[tuple[str, bytes]]:
    """Frames reais de câmera pública da CET — mesma origem que a produção."""
    candidatos = [
        PROJECT_ROOT / "ml" / "datasets" / "holdout_0902",
        PROJECT_ROOT / "ml" / "datasets" / "negativos_cet",
    ]
    arquivos: list[Path] = []
    for pasta in candidatos:
        if pasta.is_dir():
            arquivos = sorted(pasta.glob("*.jpg"))
            if arquivos:
                break
    if not arquivos:
        avulso = BACKEND_DIR / "data" / "cet_225_current.jpg"
        if avulso.is_file():
            arquivos = [avulso]
    if not arquivos:
        raise SystemExit("Nenhum frame de câmera encontrado para medir.")
    if limite:
        arquivos = arquivos[:limite]
    return [(caminho.name, caminho.read_bytes()) for caminho in arquivos]


def _ambiente() -> dict:
    import torch

    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    try:
        import psutil

        memoria_gb = round(psutil.virtual_memory().total / 1024**3, 1)
        nucleos = psutil.cpu_count(logical=False)
    except Exception:
        memoria_gb, nucleos = None, os.cpu_count()
    return {
        "medido_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "so": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "nucleos_fisicos": nucleos,
        "memoria_gb": memoria_gb,
        "gpu": gpu,
        "cuda_disponivel": torch.cuda.is_available(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "modelo_transito": ml_detector._model_path(),
        "modelo_alagamento": ml_detector._incident_model_path(),
        "imgsz": ml_detector._imgsz(),
        "conf_transito": settings.yolo_threshold,
        "conf_alagamento": settings.gx_yolo_incident_conf,
    }


# --------------------------------------------------------------------------- #
# Servidor local (para as etapas de HTTP e WebSocket)
# --------------------------------------------------------------------------- #

def _subir_servidor():
    import uvicorn

    from app.main import app as fastapi_app

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=PORTA, log_level="error", access_log=False)
    servidor = uvicorn.Server(config)
    thread = threading.Thread(target=servidor.run, daemon=True)
    thread.start()
    limite = time.monotonic() + 60
    while not servidor.started and time.monotonic() < limite:
        time.sleep(0.05)
    if not servidor.started:
        raise SystemExit("uvicorn não subiu na porta %d" % PORTA)
    return servidor


# --------------------------------------------------------------------------- #
# Blocos de medição
# --------------------------------------------------------------------------- #

def bloco_carga_modelos() -> list[dict]:
    """Custo de partida a frio: acontece uma vez, na primeira inferência."""
    linhas: list[dict] = []

    inicio = time.perf_counter()
    modelo = ml_detector._load_model()
    if modelo is not None:
        linhas.append(_resumir("Carga do peso de transito (yolo11m, 1x)", [(time.perf_counter() - inicio) * 1000], "partida a frio"))

    inicio = time.perf_counter()
    incidente = ml_detector._load_incident_model()
    if incidente is not None:
        linhas.append(_resumir("Carga do peso de alagamento (1x)", [(time.perf_counter() - inicio) * 1000], "partida a frio"))
    return linhas


def bloco_inferencia(frames: list[tuple[str, bytes]], repeticoes: int) -> list[dict]:
    """Inferência YOLO isolada — a etapa que domina a latência do pipeline."""
    linhas: list[dict] = []
    caminhos = []
    for nome, conteudo in frames:
        destino = _TEMP_DIR / nome
        destino.write_bytes(conteudo)
        caminhos.append(str(destino))

    # Primeira inferência separada: inclui alocação de CUDA e warm-up do grafo.
    inicio = time.perf_counter()
    ml_detector.detectar_imagem_real(caminhos[0], settings.yolo_threshold)
    linhas.append(_resumir("Primeira inferencia apos a carga (warm-up CUDA, 1x)", [(time.perf_counter() - inicio) * 1000], "nao se repete"))
    for caminho in caminhos[:3]:
        ml_detector.detectar_imagem_real(caminho, settings.yolo_threshold)

    amostras = _cronometrar(lambda c: ml_detector.detectar_imagem_real(c, settings.yolo_threshold), caminhos, repeticoes)
    linhas.append(_resumir("Inferencia YOLO11m @%d (contagem de veiculos)" % ml_detector._imgsz(), amostras, "GPU"))

    ml_detector.detectar_incidentes_imagem(caminhos[0], settings.gx_yolo_incident_conf)
    amostras = _cronometrar(lambda c: ml_detector.detectar_incidentes_imagem(c, settings.gx_yolo_incident_conf), caminhos, repeticoes)
    linhas.append(_resumir("Inferencia do modelo de alagamento", amostras, "GPU"))
    return linhas


def bloco_cpu(frames: list[tuple[str, bytes]], amostras_cpu: int) -> list[dict]:
    """Mesma chamada de predict em GPU e em CPU, para comparação de hardware."""
    from ultralytics import YOLO

    caminhos = [str(_TEMP_DIR / nome) for nome, _ in frames[:amostras_cpu]]
    imgsz = ml_detector._imgsz()
    conf = settings.yolo_threshold
    linhas: list[dict] = []

    def _predizer(modelo, dispositivo):
        def _executar(caminho):
            resultado = modelo.predict(source=caminho, conf=conf, imgsz=imgsz, device=dispositivo, verbose=False)
            # Força a sincronização com a GPU: sem ler as caixas o predict
            # retorna antes de o kernel terminar e o tempo sai menor que o real.
            for item in resultado:
                _ = len(item.boxes)
        return _executar

    modelo_gpu = ml_detector._load_model()
    executar_gpu = _predizer(modelo_gpu, 0)
    executar_gpu(caminhos[0])
    linhas.append(_resumir("predict() em GPU (mesma chamada)", _cronometrar(executar_gpu, caminhos, 1), "com CUDA"))

    modelo_cpu = YOLO(ml_detector._model_path())
    executar_cpu = _predizer(modelo_cpu, "cpu")
    executar_cpu(caminhos[0])
    linhas.append(_resumir("predict() em CPU (mesma chamada)", _cronometrar(executar_cpu, caminhos, 1), "sem CUDA"))
    return linhas


def bloco_pipeline(frames: list[tuple[str, bytes]], repeticoes: int) -> list[dict]:
    """Serviço de validação completo: arquivo temporário + inferência + dedupe."""
    servico = VisualValidationService()

    def _validar(par):
        _, conteudo = par
        servico.validate_frame(conteudo, "image/jpeg", uuid.uuid4().hex, settings.yolo_threshold)

    _validar(frames[0])
    amostras = _cronometrar(_validar, frames, repeticoes)
    return [_resumir("Validacao do frame (temp + inferencia + deduplicacao)", amostras, "latencia_ms da API")]


def bloco_persistencia(frames: list[tuple[str, bytes]], repeticoes: int) -> list[dict]:
    """Gravação da evidência e do evento, e recálculo da fusão de dados."""
    from app.database import Base, SessionLocal, engine
    from ml.detector import Deteccao

    Base.metadata.create_all(bind=engine)
    deteccao = Deteccao(classe_id=8, nome="veiculo", confianca=0.87, severidade="baixa", tipo="observacao_visual", bbox=(10, 10, 120, 90), classe_modelo="car")

    amostras_persistencia: list[float] = []
    amostras_fusao: list[float] = []
    ids: list[int] = []
    with SessionLocal() as db:
        for _ in range(repeticoes):
            for _, conteudo in frames:
                inicio = time.perf_counter()
                evento = registrar_deteccao(db, deteccao, conteudo, -23.5975, -46.6508, origem="benchmark")
                amostras_persistencia.append((time.perf_counter() - inicio) * 1000)
                ids.append(evento.id)
        for evento_id in ids:
            inicio = time.perf_counter()
            aplicar_fusao_evento(db, evento_id, persistir=True)
            amostras_fusao.append((time.perf_counter() - inicio) * 1000)

    return [
        _resumir("Persistencia do evento + evidencia anotada (2 JPEG + commit)", amostras_persistencia, "SQLite/WAL"),
        _resumir("Fusao de dados (IA + clima + fonte oficial) e gravacao", amostras_fusao, "SQLite/WAL"),
    ]


def bloco_http(frames: list[tuple[str, bytes]], repeticoes: int) -> list[dict]:
    """Ida e volta HTTP contra o uvicorn local, incluindo upload multipart."""
    linhas: list[dict] = []
    with httpx.Client(base_url="http://127.0.0.1:%d" % PORTA, timeout=120.0) as cliente:
        cliente.get("/health")
        amostras = []
        for _ in range(30):
            inicio = time.perf_counter()
            cliente.get("/health")
            amostras.append((time.perf_counter() - inicio) * 1000)
        linhas.append(_resumir("GET /health (piso da rede local + ASGI)", amostras, "127.0.0.1"))

        cliente.get("/eventos")
        amostras = []
        for _ in range(30):
            inicio = time.perf_counter()
            cliente.get("/eventos")
            amostras.append((time.perf_counter() - inicio) * 1000)
        linhas.append(_resumir("GET /eventos (carga do painel)", amostras, "127.0.0.1"))

        def _enviar(par):
            _, conteudo = par
            resposta = cliente.post(
                "/deteccao/frame",
                files={"file": ("frame.jpg", conteudo, "image/jpeg")},
                data={"frame_id": uuid.uuid4().hex},
            )
            resposta.raise_for_status()

        _enviar(frames[0])
        amostras = _cronometrar(_enviar, frames, repeticoes)
        linhas.append(_resumir("POST /deteccao/frame ponta a ponta (HTTP)", amostras, "127.0.0.1"))
    return linhas


async def _medir_ws_cv(frames: list[tuple[str, bytes]], repeticoes: int) -> list[float]:
    """Canal de câmera do navegador: envia o frame em base64 e espera a resposta."""
    intervalo = 1 / settings.yolo_max_fps + 0.05
    amostras: list[float] = []
    async with websockets.connect("ws://127.0.0.1:%d/ws/cv" % PORTA, max_size=None) as ws:
        await ws.recv()  # {"tipo": "pronto"}
        for _ in range(repeticoes):
            for _, conteudo in frames:
                await asyncio.sleep(intervalo)  # respeita o limitador de FPS do servidor
                mensagem = json.dumps({
                    "tipo": "frame",
                    "conteudo": base64.b64encode(conteudo).decode(),
                    "mime": "image/jpeg",
                    "frame_id": uuid.uuid4().hex,
                })
                inicio = time.perf_counter()
                await ws.send(mensagem)
                resposta = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                decorrido = (time.perf_counter() - inicio) * 1000
                if resposta.get("tipo") == "frame_resultado":
                    amostras.append(decorrido)
    return amostras


async def _medir_ponta_a_ponta(frames: list[tuple[str, bytes]], quantidade: int) -> tuple[list[float], list[float]]:
    """Upload -> inferência -> evento gravado -> mensagem no painel via WebSocket."""
    totais: list[float] = []
    propagacoes: list[float] = []
    with httpx.Client(base_url="http://127.0.0.1:%d" % PORTA, timeout=120.0) as cliente:
        async with websockets.connect("ws://127.0.0.1:%d/ws" % PORTA, max_size=None) as ws:
            await ws.recv()  # {"tipo": "pronto"}
            for indice in range(quantidade):
                _, conteudo = frames[indice % len(frames)]
                inicio = time.perf_counter()
                resposta = await asyncio.to_thread(
                    cliente.post,
                    "/deteccao/confirmar",
                    files={"file": ("frame.jpg", conteudo, "image/jpeg")},
                    data={
                        "nome": "veiculo",
                        "confianca": "0.9",
                        "severidade": "baixa",
                        "tipo": "observacao_visual",
                        "latitude": "-23.5975",
                        "longitude": "-46.6508",
                    },
                )
                if resposta.status_code >= 400:
                    continue
                while True:
                    mensagem = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                    if mensagem.get("tipo") == "evento_criado":
                        break
                chegada = time.perf_counter()
                totais.append((chegada - inicio) * 1000)
                emitido = datetime.fromisoformat(mensagem["timestamp"])
                propagacoes.append(max(0.0, (datetime.now(UTC) - emitido).total_seconds() * 1000))
    return totais, propagacoes


def bloco_rede(quantidade: int) -> list[dict]:
    """Download do snapshot público da CET — a única etapa fora da máquina."""
    from app.services.cet_camera_catalog import CAMERAS

    linhas: list[dict] = []
    amostras: list[float] = []
    tamanhos: list[int] = []
    with httpx.Client(timeout=15.0, headers={"User-Agent": "Mozilla/5.0 (MotSP benchmark)"}) as cliente:
        for indice in range(quantidade):
            camera = CAMERAS[indice % len(CAMERAS)]
            try:
                inicio = time.perf_counter()
                resposta = cliente.get(camera.snapshot_url)
                resposta.raise_for_status()
                amostras.append((time.perf_counter() - inicio) * 1000)
                tamanhos.append(len(resposta.content))
            except Exception as erro:
                print("  aviso: falha ao baixar %s (%s)" % (camera.snapshot_url, erro))
    if amostras:
        nota = "JPEG medio de %.0f kB" % (statistics.fmean(tamanhos) / 1024)
        linhas.append(_resumir("Download do snapshot da camera CET-SP", amostras, nota))
    return linhas


# --------------------------------------------------------------------------- #
# Saída
# --------------------------------------------------------------------------- #

def _imprimir(titulo: str, linhas: list[dict]) -> None:
    if not linhas:
        return
    largura = max(len(linha["etapa"]) for linha in linhas)
    print("\n" + titulo)
    print("-" * (largura + 44))
    print("%-*s  %4s  %8s  %8s  %8s  %8s" % (largura, "Etapa", "n", "media", "p50", "p95", "max"))
    print("-" * (largura + 44))
    for linha in linhas:
        print("%-*s  %4d  %8.1f  %8.1f  %8.1f  %8.1f" % (
            largura, linha["etapa"], linha["n"], linha["media"], linha["p50"], linha["p95"], linha["max"],
        ))
    print("-" * (largura + 44))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mede a latencia real do pipeline do MotSP.")
    parser.add_argument("--repeticoes", type=int, default=3, help="passadas sobre o conjunto de frames (padrao: 3)")
    parser.add_argument("--amostras", type=int, default=20, help="frames distintos usados (padrao: 20)")
    parser.add_argument("--cpu", action="store_true", help="inclui a comparacao CPU x GPU (lento)")
    parser.add_argument("--amostras-cpu", type=int, default=8, help="frames medidos em CPU (padrao: 8)")
    parser.add_argument("--rede", action="store_true", help="baixa snapshots reais da CET-SP (usa internet)")
    parser.add_argument("--e2e", type=int, default=10, help="medicoes ponta a ponta upload->painel (padrao: 10)")
    parser.add_argument("--json", type=str, default="", help="arquivo para gravar o resultado completo")
    argumentos = parser.parse_args()

    frames = _frames(argumentos.amostras)
    ambiente = _ambiente()
    print("MotSP - medicao de latencia")
    print("=" * 60)
    for chave, valor in ambiente.items():
        print("  %-20s %s" % (chave + ":", valor))
    print("  %-20s %d (cameras CET-SP)" % ("frames:", len(frames)))

    resultado: dict[str, list[dict]] = {}
    resultado["partida"] = bloco_carga_modelos()
    resultado["inferencia"] = bloco_inferencia(frames, argumentos.repeticoes)
    resultado["pipeline"] = bloco_pipeline(frames, argumentos.repeticoes)
    resultado["persistencia"] = bloco_persistencia(frames[: min(len(frames), 10)], 1)
    if argumentos.cpu:
        resultado["hardware"] = bloco_cpu(frames, argumentos.amostras_cpu)

    servidor = _subir_servidor()
    try:
        resultado["http"] = bloco_http(frames, argumentos.repeticoes)
        amostras_ws = asyncio.run(_medir_ws_cv(frames[: min(len(frames), 10)], 1))
        resultado["websocket"] = [_resumir("WS /ws/cv - frame do navegador e resposta", amostras_ws, "base64, limitado a %d FPS" % settings.yolo_max_fps)]
        totais, propagacoes = asyncio.run(_medir_ponta_a_ponta(frames, argumentos.e2e))
        resultado["ponta_a_ponta"] = []
        if propagacoes:
            resultado["ponta_a_ponta"].append(_resumir("Broadcast do evento ate o painel (WebSocket)", propagacoes, "so a propagacao"))
        if totais:
            resultado["ponta_a_ponta"].append(_resumir("Upload -> inferencia -> evento no painel", totais, "caminho completo"))
    finally:
        servidor.should_exit = True
        time.sleep(1.0)

    if argumentos.rede:
        resultado["rede"] = bloco_rede(10)

    titulos = {
        "partida": "PARTIDA A FRIO (uma vez por processo)",
        "inferencia": "INFERENCIA (regime permanente)",
        "hardware": "COMPARACAO DE HARDWARE",
        "pipeline": "PIPELINE DE VALIDACAO",
        "persistencia": "PERSISTENCIA E FUSAO",
        "http": "API HTTP",
        "websocket": "WEBSOCKET",
        "ponta_a_ponta": "PONTA A PONTA",
        "rede": "REDE EXTERNA",
    }
    for chave, titulo in titulos.items():
        _imprimir(titulo, resultado.get(chave, []))
    print("\nTempos em milissegundos.")

    if argumentos.json:
        destino = Path(argumentos.json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"ambiente": ambiente, "medicoes": resultado}, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Resultado completo em %s" % destino)


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
