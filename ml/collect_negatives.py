"""Baixa imagens das câmeras da CET-SP sem alagamento, para usar no treino.

Essas imagens ensinam o modelo de alagamento a reconhecer uma rua normal. Antes
delas o modelo via alagamento em quase toda imagem.

    python ml/collect_negatives.py --hours 12
    python ml/collect_negatives.py --out ml/datasets/negativos_cet --interval 30 --hours 8
    python ml/collect_negatives.py --cameras 22,23,180 --max-per-camera 150

Sem --hours, roda até apertar Ctrl+C. Vale rodar em horários diferentes (dia,
noite e chuva sem alagamento). Antes de usar as imagens, confira a pasta e
apague as que tiverem água acumulada de verdade.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

_CATALOGO_PATH = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "cet_camera_catalog.py"


def _carregar_catalogo():
    """Carrega só o catálogo de câmeras, sem precisar subir o backend."""
    spec = importlib.util.spec_from_file_location("cet_camera_catalog", _CATALOGO_PATH)
    modulo = importlib.util.module_from_spec(spec)
    # Sem registrar o módulo, a dataclass dá erro ao carregar o arquivo sozinho.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


catalogo = _carregar_catalogo()

_parar = False


def _sig_handler(_signum, _frame) -> None:
    global _parar
    _parar = True
    print("\nEncerrando após a rodada atual...")


def _hashes_existentes(pasta: Path) -> set[str]:
    """Hash das imagens já salvas, para não salvar a mesma imagem duas vezes."""
    vistos: set[str] = set()
    for arquivo in pasta.glob("*.jpg"):
        try:
            vistos.add(hashlib.sha256(arquivo.read_bytes()).hexdigest())
        except OSError:
            continue
    return vistos


def coletar(args: argparse.Namespace) -> None:
    import httpx

    saida = Path(args.out)
    saida.mkdir(parents=True, exist_ok=True)

    cameras = catalogo.CAMERAS
    if args.cameras:
        ids = {int(x) for x in args.cameras.split(",")}
        cameras = tuple(cam for cam in cameras if cam.id in ids)
    if not cameras:
        raise SystemExit("Nenhuma câmera selecionada.")

    vistos = _hashes_existentes(saida)
    por_camera: dict[int, int] = {}
    for arquivo in saida.glob("cam*.jpg"):
        try:
            cam_id = int(arquivo.name.split("_", 1)[0][3:])
        except (ValueError, IndexError):
            continue
        por_camera[cam_id] = por_camera.get(cam_id, 0) + 1

    limite_tempo = time.monotonic() + args.hours * 3600 if args.hours else None
    salvos = 0
    rodadas = 0
    print(
        f"Coletando de {len(cameras)} câmera(s) para {saida}, intervalo {args.interval}s, "
        + (f"{args.hours}h" if args.hours else "até Ctrl+C")
        + f" | {len(vistos)} frame(s) já na pasta"
    )

    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (MotSP collect-negatives)"}) as client:
        while not _parar:
            rodadas += 1
            for cam in cameras:
                if _parar:
                    break
                if args.max_per_camera and por_camera.get(cam.id, 0) >= args.max_per_camera:
                    continue
                try:
                    resp = client.get(cam.snapshot_url)
                    resp.raise_for_status()
                    conteudo = resp.content
                except httpx.HTTPError as exc:
                    print(f"  [{cam.id}] falha HTTP: {exc}")
                    continue

                if catalogo.frame_esta_desatualizado(resp.headers, args.frescor_max_segundos):
                    continue
                if not conteudo or len(conteudo) < 2000:
                    continue

                digest = hashlib.sha256(conteudo).hexdigest()
                if digest in vistos:
                    continue
                vistos.add(digest)

                nome = f"cam{cam.id}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
                (saida / nome).write_bytes(conteudo)
                por_camera[cam.id] = por_camera.get(cam.id, 0) + 1
                salvos += 1

            if limite_tempo and time.monotonic() >= limite_tempo:
                break
            if _parar:
                break

            # Espera em pedaços curtos para o Ctrl+C responder rápido
            fim_espera = time.monotonic() + args.interval
            while time.monotonic() < fim_espera and not _parar:
                time.sleep(min(1.0, fim_espera - time.monotonic()))

    print(f"\n{salvos} frame(s) novos salvos em {rodadas} rodada(s). Total na pasta por câmera:")
    for cam in cameras:
        print(f"  [{cam.id}] {cam.nome}: {por_camera.get(cam.id, 0)}")
    print(
        "\nRevise a pasta e apague frames com água acumulada antes de usar em:\n"
        f"  train_incident_model.py merge --flood ... --negatives {saida} --out ml/datasets/incidentes"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="ml/datasets/negativos_cet", help="Pasta de saída")
    parser.add_argument("--interval", type=float, default=30.0, help="Segundos entre rodadas de coleta")
    parser.add_argument("--hours", type=float, default=None, help="Duração total; sem isso, roda até Ctrl+C")
    parser.add_argument("--cameras", default=None, help="IDs de câmera separados por vírgula (padrão: todas)")
    parser.add_argument("--max-per-camera", type=int, default=None, help="Para de salvar de uma câmera ao atingir N frames")
    parser.add_argument("--frescor-max-segundos", type=float, default=600.0, help="Descarta frame com Last-Modified mais velho que isto")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _sig_handler)
    try:
        coletar(args)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
