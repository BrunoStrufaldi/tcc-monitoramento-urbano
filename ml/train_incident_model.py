"""Treina o modelo dedicado a alagamento/árvore caída (ml/models/gx-incident.pt).

Roda em 4 passos porque as classes reais de cada dataset do Roboflow só se
sabe depois de baixar (a página não é acessível sem login) — então primeiro
inspeciona, decide o mapeamento, e só então funde e treina.

    python ml/train_incident_model.py inspect --workspace <ws> --project <proj>
    python ml/train_incident_model.py download --workspace <ws> --project <proj> --version <n> --out ml/datasets/flood
    python ml/train_incident_model.py merge --flood ml/datasets/flood --flood-classes "flood" --tree ml/datasets/tree --tree-classes "fallen tree,fall" --out ml/datasets/incidentes
    python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 80

Requer `pip install roboflow` (já em requirements-yolo.txt) e a variável de
ambiente ROBOFLOW_API_KEY (roboflow.com/settings/api, plano gratuito).
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
from pathlib import Path

import yaml

CLASSES_ALVO = ["alagamento", "arvore_caida"]


def _api_key() -> str:
    key = os.getenv("ROBOFLOW_API_KEY")
    if not key:
        raise SystemExit("Defina ROBOFLOW_API_KEY no ambiente (roboflow.com/settings/api).")
    return key


def cmd_inspect(args: argparse.Namespace) -> None:
    from roboflow import Roboflow

    rf = Roboflow(api_key=_api_key())
    project = rf.workspace(args.workspace).project(args.project)
    print(f"Projeto: {project.name}")
    for versao in project.versions():
        print(f"  versão {versao.version} — {getattr(versao, 'images', '?')} imagens")


def cmd_download(args: argparse.Namespace) -> None:
    from roboflow import Roboflow

    rf = Roboflow(api_key=_api_key())
    project = rf.workspace(args.workspace).project(args.project)
    versao = project.version(args.version)
    versao.download("yolov8", location=args.out)
    print(f"Baixado em {args.out}")


def _ler_names(dataset_dir: Path) -> list[str]:
    with open(dataset_dir / "data.yaml", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)["names"]


def _fundir_split(origem: Path, destino: Path, split: str, prefixo: str, names: list[str], classes_incluidas: set[str], indice_alvo: int) -> int:
    imagens_src = origem / split / "images"
    labels_src = origem / split / "labels"
    if not imagens_src.is_dir():
        return 0

    imagens_dst = destino / split / "images"
    labels_dst = destino / split / "labels"
    imagens_dst.mkdir(parents=True, exist_ok=True)
    labels_dst.mkdir(parents=True, exist_ok=True)

    total = 0
    for imagem in imagens_src.iterdir():
        if not imagem.is_file():
            continue
        novo_nome = f"{prefixo}_{imagem.name}"
        shutil.copy2(imagem, imagens_dst / novo_nome)

        label_src = labels_src / (imagem.stem + ".txt")
        linhas_novas: list[str] = []
        if label_src.is_file():
            for linha in label_src.read_text(encoding="utf-8").splitlines():
                partes = linha.split()
                if not partes:
                    continue
                classe_id = int(partes[0])
                nome_classe = names[classe_id].strip() if classe_id < len(names) else None
                if nome_classe not in classes_incluidas:
                    continue
                linhas_novas.append(" ".join([str(indice_alvo), *partes[1:]]))

        (labels_dst / f"{prefixo}_{imagem.stem}.txt").write_text("\n".join(linhas_novas), encoding="utf-8")
        total += 1
    return total


def _garantir_validacao(destino: Path, prefixo: str, fracao: float = 0.12) -> None:
    """Se a fonte não trouxe split de validação (ex.: dataset só com train/),
    separa uma fatia determinística do treino em vez de deixar a classe sem
    métrica de val."""
    valid_imgs = destino / "valid" / "images"
    if valid_imgs.is_dir() and any(p.name.startswith(f"{prefixo}_") for p in valid_imgs.iterdir()):
        return

    train_imgs = destino / "train" / "images"
    train_labels = destino / "train" / "labels"
    if not train_imgs.is_dir():
        return
    candidatos = sorted(p for p in train_imgs.iterdir() if p.name.startswith(f"{prefixo}_"))
    if not candidatos:
        return

    random.seed(42)
    quantidade = max(1, int(len(candidatos) * fracao))
    escolhidos = random.sample(candidatos, quantidade)

    valid_imgs.mkdir(parents=True, exist_ok=True)
    valid_labels = destino / "valid" / "labels"
    valid_labels.mkdir(parents=True, exist_ok=True)
    for imagem in escolhidos:
        shutil.move(str(imagem), str(valid_imgs / imagem.name))
        label = train_labels / (imagem.stem + ".txt")
        if label.is_file():
            shutil.move(str(label), str(valid_labels / label.name))
    print(f"{prefixo}: sem split de validação na fonte — {quantidade} imagens movidas de train para valid")


def cmd_merge(args: argparse.Namespace) -> None:
    destino = Path(args.out)
    fontes = [
        (Path(args.flood), "flood", {c.strip() for c in args.flood_classes.split(",")}, 0),
        (Path(args.tree), "tree", {c.strip() for c in args.tree_classes.split(",")}, 1),
    ]

    for origem, prefixo, classes_incluidas, indice_alvo in fontes:
        names = _ler_names(origem)
        ausentes = classes_incluidas - {n.strip() for n in names}
        if ausentes:
            print(f"AVISO: classes {ausentes} não existem em {origem}/data.yaml (names={names})")
        for split in ("train", "valid", "test"):
            total = _fundir_split(origem, destino, split, prefixo, names, classes_incluidas, indice_alvo)
            if total:
                print(f"{origem.name}/{split}: {total} imagens copiadas")
        _garantir_validacao(destino, prefixo)

    data_yaml = {
        "path": str(destino.resolve()),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(CLASSES_ALVO),
        "names": CLASSES_ALVO,
    }
    (destino / "data.yaml").write_text(yaml.safe_dump(data_yaml, allow_unicode=True), encoding="utf-8")
    print(f"data.yaml escrito em {destino}")


def cmd_train(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    modelo_base = args.base or str(Path(__file__).resolve().parent / "models" / "yolo11n.pt")
    model = YOLO(modelo_base)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=args.device,
        project=str(Path(__file__).resolve().parent / "runs"),
        name="incident",
        exist_ok=True,
    )

    melhor = Path(__file__).resolve().parent / "runs" / "incident" / "weights" / "best.pt"
    destino = Path(__file__).resolve().parent / "models" / "gx-incident.pt"
    shutil.copy2(melhor, destino)
    print(f"Pesos treinados copiados para {destino}")
    print("Ative com: set GX_YOLO_INCIDENT_MODEL=ml/models/gx-incident.pt (ou configure no backend/.env)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_inspect = sub.add_parser("inspect", help="Lista versões disponíveis de um projeto Roboflow")
    p_inspect.add_argument("--workspace", required=True)
    p_inspect.add_argument("--project", required=True)
    p_inspect.set_defaults(func=cmd_inspect)

    p_download = sub.add_parser("download", help="Baixa uma versão do dataset em formato YOLOv8")
    p_download.add_argument("--workspace", required=True)
    p_download.add_argument("--project", required=True)
    p_download.add_argument("--version", required=True, type=int)
    p_download.add_argument("--out", required=True)
    p_download.set_defaults(func=cmd_download)

    p_merge = sub.add_parser("merge", help="Funde os datasets de alagamento e árvore caída em um único conjunto de 2 classes")
    p_merge.add_argument("--flood", required=True, help="Pasta baixada do dataset de alagamento")
    p_merge.add_argument("--flood-classes", required=True, help="Nomes de classe do dataset de alagamento a mapear para 'alagamento', separados por vírgula")
    p_merge.add_argument("--tree", required=True, help="Pasta baixada do dataset de árvore caída")
    p_merge.add_argument("--tree-classes", required=True, help="Nomes de classe do dataset de árvore a mapear para 'arvore_caida', separados por vírgula")
    p_merge.add_argument("--out", required=True)
    p_merge.set_defaults(func=cmd_merge)

    p_train = sub.add_parser("train", help="Treina o YOLO11n nas 2 classes de incidente")
    p_train.add_argument("--data", required=True, help="Caminho do data.yaml fundido")
    p_train.add_argument("--epochs", type=int, default=80)
    p_train.add_argument("--imgsz", type=int, default=640)
    p_train.add_argument("--device", default="0", help="'0' para GPU CUDA, 'cpu' para CPU")
    p_train.add_argument("--base", default=None, help="Peso inicial (padrão: ml/models/yolo11n.pt)")
    p_train.set_defaults(func=cmd_train)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
