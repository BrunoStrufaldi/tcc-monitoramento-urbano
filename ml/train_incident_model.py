"""Treina o modelo dedicado a **alagamento** (ml/models/gx-incident.pt).

Uma classe só (`alagamento`). A classe `arvore_caida` foi tirada do escopo do
TCC e o app já descartava qualquer detecção dela (`ml/detector.py`); mantê-la no
treino só desbalanceava o dataset (era ~5% das instâncias) e confundia o
classificador, então saiu daqui também.

Fluxo em 4 passos — as classes reais de cada dataset do Roboflow só se sabe
depois de baixar (a página não abre sem login), então primeiro inspeciona,
decide o mapeamento, e só então funde e treina:

    python ml/train_incident_model.py inspect --workspace <ws> --project <proj>
    python ml/train_incident_model.py download --workspace <ws> --project <proj> --version <n> --out ml/datasets/flood
    python ml/train_incident_model.py merge --flood ml/datasets/flood --out ml/datasets/incidentes --negatives ml/datasets/negativos_cet
    python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 120

`merge` aceita:
- vários `--flood DIR` (repetível), cada um com um `--flood-classes` opcional
  na mesma ordem; sem `--flood-classes` ou com `"*"`, todas as classes da
  fonte viram `alagamento`.
- vários `--negatives DIR` (repetível): imagens de rua **sem** alagamento
  (frame de câmera CET em tempo seco, noite, chuva sem alagar). Entram com
  label vazio — YOLO trata como fundo. Sem negativos o modelo aprende que
  "toda imagem tem alagamento em algum canto" e passa a alucinar caixa no
  nada (era o comportamento observado antes deste retreino).

Requer `pip install -r backend/requirements-yolo.txt` e, só para inspect/
download, a variável de ambiente ROBOFLOW_API_KEY (roboflow.com/settings/api,
plano gratuito).
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
from pathlib import Path

import yaml

# Windows: o console herda cp1252 e os prints com acento/seta quebram
# (UnicodeEncodeError). Força UTF-8 na saída.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CLASSE_ALVO = "alagamento"
CLASSES_ALVO = [CLASSE_ALVO]
_EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_SPLITS = ("train", "valid", "test")


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


def _iter_imagens(pasta: Path):
    for caminho in sorted(pasta.rglob("*")):
        if caminho.is_file() and caminho.suffix.lower() in _EXTENSOES_IMAGEM:
            yield caminho


def _linha_para_bbox(coords: list[str], indice_alvo: int) -> str | None:
    """Normaliza uma linha de rótulo YOLO para detecção (`classe cx cy w h`).

    Datasets do Roboflow marcados como segmentação exportam polígono
    (`classe x1 y1 x2 y2 ...`); um arquivo com linha de bbox e linha de
    polígono junto faz o Ultralytics descartar a imagem inteira como
    "corrupt: labels mix segment and detection rows". Aqui todo polígono
    vira sua caixa envolvente.
    """
    try:
        valores = [float(v) for v in coords]
    except ValueError:
        return None
    if len(valores) == 4:
        cx, cy, w, h = valores
    elif len(valores) >= 6 and len(valores) % 2 == 0:
        xs = valores[0::2]
        ys = valores[1::2]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
    else:
        return None
    cx, cy = min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0)
    w, h = min(w, 1.0), min(h, 1.0)
    if w <= 0 or h <= 0:
        return None
    return f"{indice_alvo} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def _fundir_split(
    origem: Path,
    destino: Path,
    split: str,
    prefixo: str,
    names: list[str],
    classes_incluidas: set[str] | None,
    indice_alvo: int = 0,
) -> tuple[int, int]:
    """Copia um split de uma fonte, remapeando toda classe incluída para
    ``indice_alvo``. ``classes_incluidas=None`` inclui todas. Retorna
    ``(imagens, imagens_sem_caixa)``."""
    imagens_src = origem / split / "images"
    labels_src = origem / split / "labels"
    if not imagens_src.is_dir():
        return 0, 0

    imagens_dst = destino / split / "images"
    labels_dst = destino / split / "labels"
    imagens_dst.mkdir(parents=True, exist_ok=True)
    labels_dst.mkdir(parents=True, exist_ok=True)

    total = sem_caixa = 0
    for imagem in imagens_src.iterdir():
        if not imagem.is_file() or imagem.suffix.lower() not in _EXTENSOES_IMAGEM:
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
                classe_id = int(float(partes[0]))
                nome_classe = names[classe_id].strip() if classe_id < len(names) else None
                if classes_incluidas is not None and nome_classe not in classes_incluidas:
                    continue
                bbox = _linha_para_bbox(partes[1:], indice_alvo)
                if bbox is not None:
                    linhas_novas.append(bbox)

        (labels_dst / f"{prefixo}_{imagem.stem}.txt").write_text("\n".join(linhas_novas), encoding="utf-8")
        total += 1
        if not linhas_novas:
            sem_caixa += 1
    return total, sem_caixa


def _garantir_validacao(destino: Path, prefixo: str, fracao: float = 0.12) -> None:
    """Se a fonte não trouxe split de validação, separa uma fatia determinística
    do treino em vez de deixar a fonte sem métrica de val."""
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
    print(f"  {prefixo}: sem split de validação na fonte — {quantidade} imagens movidas de train para valid")


def _adicionar_negativos(destino: Path, pastas: list[Path], val_fraction: float, prefixo: str = "neg") -> tuple[int, int]:
    """Copia imagens de fundo (rua sem alagamento) com label .txt vazio.
    Uma fração vai para valid, o resto para train. Retorna (train, valid)."""
    todas: list[Path] = []
    for pasta in pastas:
        if not pasta.is_dir():
            print(f"  AVISO: pasta de negativos {pasta} não existe — ignorada")
            continue
        todas.extend(_iter_imagens(pasta))
    if not todas:
        return 0, 0

    random.seed(1234)
    random.shuffle(todas)
    corte = max(1, int(len(todas) * val_fraction)) if len(todas) > 1 else 0
    destino_split = {"valid": todas[:corte], "train": todas[corte:]}

    contagem = {}
    for split, imagens in destino_split.items():
        imagens_dst = destino / split / "images"
        labels_dst = destino / split / "labels"
        imagens_dst.mkdir(parents=True, exist_ok=True)
        labels_dst.mkdir(parents=True, exist_ok=True)
        for indice, imagem in enumerate(imagens):
            nome = f"{prefixo}_{indice:06d}{imagem.suffix.lower()}"
            shutil.copy2(imagem, imagens_dst / nome)
            (labels_dst / f"{prefixo}_{indice:06d}.txt").write_text("", encoding="utf-8")
        contagem[split] = len(imagens)
    return contagem.get("train", 0), contagem.get("valid", 0)


def _contar_instancias(destino: Path, split: str) -> tuple[int, int, int]:
    """(imagens, imagens_com_caixa, total_caixas) de um split fundido."""
    labels = destino / split / "labels"
    if not labels.is_dir():
        return 0, 0, 0
    imagens = com_caixa = caixas = 0
    for arquivo in labels.glob("*.txt"):
        imagens += 1
        linhas = [linha for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]
        if linhas:
            com_caixa += 1
            caixas += len(linhas)
    return imagens, com_caixa, caixas


def cmd_merge(args: argparse.Namespace) -> None:
    destino = Path(args.out)
    if destino.exists() and args.limpar:
        shutil.rmtree(destino)
        print(f"Diretório {destino} limpo antes da fusão")

    classes_por_fonte = args.flood_classes or []
    for indice, flood_dir in enumerate(args.flood):
        origem = Path(flood_dir)
        names = _ler_names(origem)
        bruto = classes_por_fonte[indice] if indice < len(classes_por_fonte) else "*"
        if bruto.strip() == "*":
            classes_incluidas: set[str] | None = None
            print(f"{origem.name}: todas as {len(names)} classes → '{CLASSE_ALVO}' ({names})")
        else:
            classes_incluidas = {c.strip() for c in bruto.split(",")}
            ausentes = classes_incluidas - {n.strip() for n in names}
            if ausentes:
                print(f"AVISO: classes {ausentes} não existem em {origem}/data.yaml (names={names})")

        prefixo = f"flood{indice}"
        for split in _SPLITS:
            total, sem_caixa = _fundir_split(origem, destino, split, prefixo, names, classes_incluidas)
            if total:
                print(f"  {origem.name}/{split}: {total} imagens ({sem_caixa} sem caixa)")
        _garantir_validacao(destino, prefixo)

    if args.negatives:
        neg_train, neg_valid = _adicionar_negativos(destino, [Path(p) for p in args.negatives], args.neg_val_fraction)
        print(f"Negativos (fundo, label vazio): {neg_train} em train, {neg_valid} em valid")

    data_yaml = {
        "path": str(destino.resolve()),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(CLASSES_ALVO),
        "names": CLASSES_ALVO,
    }
    (destino / "data.yaml").write_text(yaml.safe_dump(data_yaml, allow_unicode=True), encoding="utf-8")

    print(f"\ndata.yaml escrito em {destino}")
    for split in ("train", "valid"):
        imagens, com_caixa, caixas = _contar_instancias(destino, split)
        if imagens:
            frac_neg = (imagens - com_caixa) / imagens
            print(
                f"  {split}: {imagens} imagens | {com_caixa} com alagamento ({caixas} caixas) | "
                f"{imagens - com_caixa} negativos ({frac_neg:.0%})"
            )
    imagens_tr, com_caixa_tr, _ = _contar_instancias(destino, "train")
    if imagens_tr:
        frac = (imagens_tr - com_caixa_tr) / imagens_tr
        if frac < 0.2:
            print(
                "\nAVISO: menos de 20% de imagens negativas no treino. "
                "Adicione mais com --negatives ou o modelo tende a alucinar alagamento em cena seca."
            )


def _resolver_base(nome: str) -> str:
    """Aceita caminho de arquivo existente ou nome de peso oficial Ultralytics
    (ex.: 'yolo11s.pt'). Nome oficial é salvo/reaproveitado em ml/models/."""
    caminho = Path(nome)
    if caminho.is_file():
        return str(caminho)
    modelos_dir = Path(__file__).resolve().parent / "models"
    local = modelos_dir / caminho.name
    if local.is_file():
        return str(local)
    # Nome oficial: deixa o Ultralytics baixar dentro de ml/models/.
    from ultralytics import YOLO

    modelos_dir.mkdir(parents=True, exist_ok=True)
    baixado = YOLO(caminho.name).ckpt_path or str(local)
    destino = modelos_dir / Path(baixado).name
    if Path(baixado).resolve() != destino.resolve():
        shutil.copy2(baixado, destino)
    return str(destino)


def cmd_train(args: argparse.Namespace) -> None:
    from ultralytics import YOLO

    modelo_base = _resolver_base(args.model or "yolo11s.pt")
    print(f"Peso inicial: {modelo_base}")
    model = YOLO(modelo_base)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=args.patience,
        # Fundo baked-erasing já aparece em alguns datasets de origem; não
        # adicionamos mais oclusão sintética por cima.
        erasing=0.0,
        close_mosaic=args.close_mosaic,
        project=str(Path(__file__).resolve().parent / "runs"),
        name=args.name,
        exist_ok=True,
    )

    origem_best = Path(__file__).resolve().parent / "runs" / args.name / "weights" / "best.pt"
    destino = Path(__file__).resolve().parent / "models" / "gx-incident.pt"
    if destino.is_file():
        backup = destino.with_name("gx-incident-anterior.pt")
        shutil.copy2(destino, backup)
        print(f"Peso atual salvo em {backup}")
    shutil.copy2(origem_best, destino)
    print(f"Pesos treinados copiados para {destino}")
    print("Ative com: set GX_YOLO_INCIDENT_MODEL=ml/models/gx-incident.pt (ou configure no backend/.env)")
    print("Valide antes de ativar: python ml/train_incident_model.py não faz isso — rode `yolo val` ou o detector")
    print("num punhado de frames CET reais e confira se caixa fantasma sumiu. Se ainda houver, suba yolo_threshold.")


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

    p_merge = sub.add_parser("merge", help="Funde uma ou mais fontes de alagamento (+ negativos) num dataset de 1 classe")
    p_merge.add_argument("--flood", action="append", required=True, help="Pasta baixada de um dataset de alagamento (repetível)")
    p_merge.add_argument(
        "--flood-classes",
        action="append",
        help="Nomes de classe a mapear para 'alagamento' numa fonte, separados por vírgula; "
        "'*' (padrão) inclui todas. Ordem casa com a dos --flood.",
    )
    p_merge.add_argument("--negatives", action="append", help="Pasta com imagens de rua SEM alagamento (repetível)")
    p_merge.add_argument("--neg-val-fraction", type=float, default=0.15, help="Fração dos negativos para o split de validação")
    p_merge.add_argument("--limpar", action="store_true", help="Apaga --out antes de fundir")
    p_merge.add_argument("--out", required=True)
    p_merge.set_defaults(func=cmd_merge)

    p_train = sub.add_parser("train", help="Treina o detector de alagamento (1 classe)")
    p_train.add_argument("--data", required=True, help="Caminho do data.yaml fundido")
    p_train.add_argument("--epochs", type=int, default=120)
    p_train.add_argument("--imgsz", type=int, default=640)
    p_train.add_argument("--batch", default=-1, type=int, help="-1 = auto (60%% da VRAM)")
    p_train.add_argument("--patience", type=int, default=30, help="Early stopping: épocas sem melhora antes de parar")
    p_train.add_argument("--close-mosaic", type=int, default=15, help="Desliga mosaic nas últimas N épocas")
    p_train.add_argument("--device", default="0", help="'0' para GPU CUDA, 'cpu' para CPU")
    p_train.add_argument("--model", default=None, help="Peso inicial (padrão: ml/models/yolo11s.pt)")
    p_train.add_argument("--name", default="incident", help="Nome da run em ml/runs/")
    p_train.set_defaults(func=cmd_train)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
