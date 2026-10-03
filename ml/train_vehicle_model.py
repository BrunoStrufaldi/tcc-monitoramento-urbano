"""Especializa o modelo de contagem de veículos nas câmeras da CET-SP.

O yolo11m (COCO) aprendeu com fotos genéricas da internet; as câmeras da CET
entregam JPEG 480x270, comprimido, com fila de carro pequeno ao fundo e cena
noturna. Aqui ele é ajustado (fine-tuning) com esses próprios frames.

Ninguém marca carro à mão: um modelo "professor" maior e lento demais para o
tempo real (yolo11x + TTA) rotula os frames, e o yolo11m — o "aluno", rápido —
aprende a imitá-lo nesse cenário (destilação por pseudo-rótulos). As 80 classes
COCO são mantidas, para o mapeamento de ``ml/detector.py`` continuar valendo.

Seguro por construção: o peso novo vai para outro arquivo e o atual não é
tocado. ``avaliar`` compara os dois em frames separados que o aluno nunca viu;
só se o novo vencer é que ``GX_YOLO_MODEL`` passa a apontar para ele.

    python ml/train_vehicle_model.py rotular
    python ml/train_vehicle_model.py treinar
    python ml/train_vehicle_model.py avaliar --novo ml/runs/veiculos/weights/best.pt
"""

from __future__ import annotations

import argparse
import hashlib
import random
import shutil
import statistics
import sys
from pathlib import Path

import yaml

for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIAS = RAIZ / "backend" / "app" / "data" / "evidencias"
DATASET = RAIZ / "ml" / "datasets" / "veiculos_cet"
MODELO_ATUAL = RAIZ / "ml" / "models" / "yolo11m.pt"
PROFESSOR = RAIZ / "ml" / "models" / "yolo11x.pt"
IMGSZ = 1280
# Mesmo limiar de produção (YOLO_THRESHOLD) para as métricas de contagem.
CONF_PRODUCAO = 0.45
# Pseudo-rótulo: um pouco abaixo do de produção para o aluno também aprender
# os carros pequenos/distantes que o professor acha com score médio.
CONF_PROFESSOR = 0.40
FRACAO_TESTE = 0.2
CLASSES_VEICULO = {2, 3, 5, 7}  # car, motorcycle, bus, truck


def _frames_unicos() -> list[Path]:
    """Frames originais das câmeras, sem duplicatas (câmera parada repete JPEG)."""
    vistos: set[str] = set()
    frames = []
    for caminho in sorted(EVIDENCIAS.glob("*-original.jpg")):
        digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
        if digest not in vistos:
            vistos.add(digest)
            frames.append(caminho)
    return frames


def cmd_rotular(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    frames = _frames_unicos()
    if not frames:
        raise SystemExit(f"Nenhum frame em {EVIDENCIAS}")
    random.Random(42).shuffle(frames)
    n_teste = max(1, int(len(frames) * FRACAO_TESTE))
    divisao = {"test": frames[:n_teste], "train": frames[n_teste:]}

    if DATASET.exists():
        shutil.rmtree(DATASET)
    professor = YOLO(str(args.professor))
    caixas = 0
    for split, lista in divisao.items():
        (DATASET / "images" / split).mkdir(parents=True)
        (DATASET / "labels" / split).mkdir(parents=True)
        for frame in lista:
            shutil.copy2(frame, DATASET / "images" / split / frame.name)
            resultado = professor.predict(str(frame), conf=CONF_PROFESSOR, imgsz=IMGSZ, augment=True, verbose=False)[0]
            linhas = [
                f"{int(c)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"
                for c, (x, y, w, h) in zip(resultado.boxes.cls.tolist(), resultado.boxes.xywhn.tolist())
            ]
            caixas += len(linhas)
            (DATASET / "labels" / split / f"{frame.stem}.txt").write_text("\n".join(linhas), encoding="utf-8")

    nomes = YOLO(str(MODELO_ATUAL)).names
    (DATASET / "data.yaml").write_text(yaml.safe_dump({
        "path": str(DATASET),
        "train": "images/train",
        "val": "images/test",
        "test": "images/test",
        "names": nomes,
    }, allow_unicode=True), encoding="utf-8")
    print(f"{len(frames)} frames únicos ({len(divisao['train'])} treino, {n_teste} teste), {caixas} caixas rotuladas")


def cmd_treinar(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    YOLO(str(MODELO_ATUAL)).train(
        data=str(DATASET / "data.yaml"),
        imgsz=IMGSZ,
        epochs=args.epochs,
        batch=args.batch,
        # Ajuste fino, não treino do zero: taxa baixa e as primeiras camadas
        # (que já sabem ver bordas/formas) congeladas, para o modelo não
        # esquecer o que sabia com só algumas centenas de frames.
        lr0=0.002,
        freeze=10,
        patience=15,
        project=str(RAIZ / "ml" / "runs"),
        name="veiculos",
        exist_ok=True,
        seed=42,
    )


def _medir(modelo_path: Path) -> dict[str, float]:
    from ultralytics import YOLO

    modelo = YOLO(str(modelo_path))
    metricas = modelo.val(data=str(DATASET / "data.yaml"), split="test", imgsz=IMGSZ,
                          classes=sorted(CLASSES_VEICULO), verbose=False, plots=False)
    medias, contagens = [], []
    for frame in sorted((DATASET / "images" / "test").glob("*.jpg")):
        resultado = modelo.predict(str(frame), conf=CONF_PRODUCAO, imgsz=IMGSZ, verbose=False)[0]
        confs = sorted((float(b.conf) for b in resultado.boxes if int(b.cls) in CLASSES_VEICULO), reverse=True)
        contagens.append(len(confs))
        if len(confs) >= 4:
            medias.append(statistics.mean(confs[:12]))
    return {
        "mAP50 (acerto x professor)": float(metricas.box.map50),
        "precisão": float(metricas.box.mp),
        "recall": float(metricas.box.mr),
        "confiança média (12 melhores)": statistics.mean(medias) if medias else 0.0,
        "veículos por frame": statistics.mean(contagens),
    }


def cmd_avaliar(args: argparse.Namespace) -> None:
    rotulos = sorted((DATASET / "labels" / "test").glob("*.txt"))
    ref = statistics.mean(
        sum(1 for linha in r.read_text().splitlines() if linha and int(linha.split()[0]) in CLASSES_VEICULO)
        for r in rotulos
    )
    atual, novo = _medir(MODELO_ATUAL), _medir(Path(args.novo))
    print(f"\nFrames de teste: {len(rotulos)} (nunca vistos no treino) · professor marca {ref:.1f} veículos/frame")
    print(f"{'métrica':32} {'atual':>8} {'novo':>8}")
    for chave in atual:
        print(f"{chave:32} {atual[chave]:8.3f} {novo[chave]:8.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rotular", help="professor rotula os frames e monta o dataset")
    p.add_argument("--professor", type=Path, default=PROFESSOR)
    p.set_defaults(func=cmd_rotular)
    p = sub.add_parser("treinar", help="ajuste fino do yolo11m no dataset")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch", type=int, default=4)
    p.set_defaults(func=cmd_treinar)
    p = sub.add_parser("avaliar", help="compara o modelo atual com o novo nos frames de teste")
    p.add_argument("--novo", required=True)
    p.set_defaults(func=cmd_avaliar)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
