"""Detecção visual real com YOLO e simulação isolada para testes/demonstração.

O detector real é carregado sob demanda para que a API continue utilizável em
ambientes sem GPU ou sem os pesos treinados. O peso COCO padrão reconhece
objetos (por exemplo, carro e ônibus), não incidentes como congestionamento,
alagamento ou incêndio. ``GX_YOLO_MODEL`` permite trocar pelos pesos urbanos.
"""

import os
import random
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CLASSES_URBANAS = {
    0: {"nome": "buraco", "severidade": "alta", "tipo": "infraestrutura"},
    1: {"nome": "alagamento", "severidade": "critica", "tipo": "clima"},
    2: {"nome": "transito", "severidade": "media", "tipo": "mobilidade"},
    3: {"nome": "lixo", "severidade": "baixa", "tipo": "meio_ambiente"},
    4: {"nome": "incendio", "severidade": "critica", "tipo": "seguranca"},
    5: {"nome": "construcao_irregular", "severidade": "alta", "tipo": "urbanismo"},
    6: {"nome": "arvore_caida", "severidade": "media", "tipo": "infraestrutura"},
    7: {"nome": "vazamento", "severidade": "alta", "tipo": "infraestrutura"},
    # Classes COCO abaixo são observações visuais. A presença de um veículo ou
    # hidrante não comprova congestionamento, acidente ou vazamento.
    8: {"nome": "veiculo", "severidade": "baixa", "tipo": "observacao_visual"},
    9: {"nome": "motocicleta", "severidade": "baixa", "tipo": "observacao_visual"},
    10: {"nome": "onibus", "severidade": "baixa", "tipo": "observacao_visual"},
    11: {"nome": "caminhao", "severidade": "baixa", "tipo": "observacao_visual"},
    12: {"nome": "hidrante", "severidade": "baixa", "tipo": "observacao_visual"},
}

_URBANAS_POR_NOME = {meta["nome"]: (identificador, meta) for identificador, meta in CLASSES_URBANAS.items()}
_COCO_PARA_URBANO = {
    "car": "veiculo",
    "motorcycle": "motocicleta",
    "bus": "onibus",
    "truck": "caminhao",
    "fire hydrant": "hidrante",
}
_model: Any | None = None
_model_error: str | None = None
_DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "yolo11n.pt"

# Modelo dedicado a alagamento/árvore caída — pesos próprios (não vêm do COCO),
# carregado separado do modelo padrão para não perder a detecção de veículos
# usada pela contagem de trânsito ao trocar de peso.
_incident_model: Any | None = None
_incident_model_error: str | None = None
_DEFAULT_INCIDENT_MODEL = Path(__file__).resolve().parent / "models" / "gx-incident.pt"


@dataclass
class Deteccao:
    """Resultado normalizado de uma detecção."""

    classe_id: int
    nome: str
    confianca: float
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int] = field(default_factory=lambda: (0, 0, 100, 100))
    classe_modelo: str | None = None


def _model_path() -> str:
    """Resolve o peso padrão sem depender do diretório de execução da API."""
    return os.getenv("GX_YOLO_MODEL", str(_DEFAULT_MODEL))


def class_mapping() -> dict[str, str]:
    """Mapeamento configurável de classes do peso para tipos urbanos GX.

    ``GX_YOLO_CLASS_MAPPING`` recebe JSON, por exemplo
    ``{"car":"veiculo","truck":"caminhao"}``. Destinos inválidos são
    ignorados para não converter uma classe desconhecida em ocorrência urbana.
    """
    mapping = dict(_COCO_PARA_URBANO)
    raw = os.getenv("GX_YOLO_CLASS_MAPPING")
    if not raw:
        return mapping
    try:
        custom = json.loads(raw)
        if isinstance(custom, dict):
            mapping.update({str(key).lower().strip(): str(value).lower().strip() for key, value in custom.items() if str(value).lower().strip() in _URBANAS_POR_NOME})
    except json.JSONDecodeError:
        pass
    return mapping


def _load_model() -> Any | None:
    """Carrega Ultralytics somente na primeira inferência."""
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error is not None:
        return None

    model_path = _model_path()
    if not Path(model_path).is_file():
        _model_error = f"Modelo não encontrado: {model_path}"
        return None
    try:
        from ultralytics import YOLO

        _model = YOLO(model_path)
        return _model
    except ImportError:
        _model_error = "Pacote ultralytics não instalado. Instale backend/requirements-yolo.txt."
    except Exception as exc:
        _model_error = f"Não foi possível carregar o modelo YOLO: {exc}"
    return None


def status_detector() -> dict[str, Any]:
    """Informa se a inferência real está disponível, sem executar a imagem."""
    model = _load_model()
    return {
        "disponivel": model is not None,
        "modo": "yolo" if model is not None else "simulacao",
        "modelo": _model_path(),
        "erro": _model_error,
        "mapeamento_padrao": class_mapping(),
        "aviso": "Pesos COCO padrão geram apenas observações de objetos. Alagamento, fumaça, incêndio e outros incidentes exigem pesos urbanos treinados e validação operacional.",
    }


def _incident_model_path() -> str:
    return os.getenv("GX_YOLO_INCIDENT_MODEL", str(_DEFAULT_INCIDENT_MODEL))


def _load_incident_model() -> Any | None:
    """Carrega o peso de incidentes (alagamento/árvore caída) sob demanda."""
    global _incident_model, _incident_model_error
    if _incident_model is not None:
        return _incident_model
    if _incident_model_error is not None:
        return None

    model_path = _incident_model_path()
    if not Path(model_path).is_file():
        _incident_model_error = f"Modelo de incidentes não encontrado: {model_path}"
        return None
    try:
        from ultralytics import YOLO

        _incident_model = YOLO(model_path)
        return _incident_model
    except ImportError:
        _incident_model_error = "Pacote ultralytics não instalado. Instale backend/requirements-yolo.txt."
    except Exception as exc:
        _incident_model_error = f"Não foi possível carregar o modelo de incidentes: {exc}"
    return None


def status_incident_detector() -> dict[str, Any]:
    """Informa se o modelo de alagamento/árvore caída está disponível, sem executar a imagem."""
    model = _load_incident_model()
    return {
        "disponivel": model is not None,
        "modelo": _incident_model_path(),
        "erro": _incident_model_error,
    }


def detectar_incidentes_imagem(caminho_imagem: str, confianca_minima: float = 0.45) -> list[Deteccao]:
    """Roda o modelo dedicado a alagamento/árvore caída — confirmação direta, não sinal indireto."""
    model = _load_incident_model()
    if model is None:
        raise RuntimeError(_incident_model_error or "Detector de incidentes indisponível")

    resultados: list[Deteccao] = []
    for resultado in model.predict(source=caminho_imagem, conf=confianca_minima, verbose=False):
        nomes = resultado.names
        for box in resultado.boxes:
            classe_modelo = int(box.cls.item())
            nome_modelo = str(nomes[classe_modelo])
            classe_urbana = _normalizar_classe(nome_modelo)
            if classe_urbana is None:
                continue
            classe_id, meta = classe_urbana
            x1, y1, x2, y2 = (int(round(valor)) for valor in box.xyxy[0].tolist())
            resultados.append(Deteccao(
                classe_id=classe_id,
                nome=meta["nome"],
                confianca=round(float(box.conf.item()), 3),
                severidade=meta["severidade"],
                tipo=meta["tipo"],
                bbox=(x1, y1, x2, y2),
                classe_modelo=nome_modelo,
            ))
    return sorted(resultados, key=lambda deteccao: deteccao.confianca, reverse=True)


def _normalizar_classe(nome_modelo: str) -> tuple[int, dict[str, str]] | None:
    nome = nome_modelo.lower().strip().replace(" ", "_")
    nome = class_mapping().get(nome_modelo.lower().strip(), nome)
    return _URBANAS_POR_NOME.get(nome)


def detectar_imagem_real(caminho_imagem: str, confianca_minima: float = 0.45) -> list[Deteccao]:
    """Executa inferência YOLO e converte classes do modelo para o domínio GX."""
    model = _load_model()
    if model is None:
        raise RuntimeError(_model_error or "Detector YOLO indisponível")

    resultados: list[Deteccao] = []
    for resultado in model.predict(source=caminho_imagem, conf=confianca_minima, verbose=False):
        nomes = resultado.names
        for box in resultado.boxes:
            classe_modelo = int(box.cls.item())
            nome_modelo = str(nomes[classe_modelo])
            classe_urbana = _normalizar_classe(nome_modelo)
            if classe_urbana is None:
                continue
            classe_id, meta = classe_urbana
            x1, y1, x2, y2 = (int(round(valor)) for valor in box.xyxy[0].tolist())
            resultados.append(Deteccao(
                classe_id=classe_id,
                nome=meta["nome"],
                confianca=round(float(box.conf.item()), 3),
                severidade=meta["severidade"],
                tipo=meta["tipo"],
                bbox=(x1, y1, x2, y2),
                classe_modelo=nome_modelo,
            ))
    return sorted(resultados, key=lambda deteccao: deteccao.confianca, reverse=True)


def detectar_imagem(caminho_imagem: str = "simulacao", num_deteccoes: int | None = None) -> list[Deteccao]:
    """Gera detecções de demonstração, usadas apenas pela rota ``/simular``."""
    if num_deteccoes is None:
        num_deteccoes = random.randint(1, 3)
    resultados: list[Deteccao] = []
    classes_disponiveis = list(CLASSES_URBANAS)
    for _ in range(min(num_deteccoes, len(classes_disponiveis))):
        classe_id = random.choice(classes_disponiveis)
        classes_disponiveis.remove(classe_id)
        meta = CLASSES_URBANAS[classe_id]
        x1, y1 = random.randint(0, 400), random.randint(0, 300)
        largura, altura = random.randint(50, 200), random.randint(50, 200)
        resultados.append(Deteccao(
            classe_id=classe_id, nome=meta["nome"], confianca=round(random.uniform(0.55, 0.98), 3),
            severidade=meta["severidade"], tipo=meta["tipo"], bbox=(x1, y1, x1 + largura, y1 + altura),
        ))
    return sorted(resultados, key=lambda deteccao: deteccao.confianca, reverse=True)


def detectar_video(frame_path: str = "simulacao_frame", frames_totais: int = 30) -> dict[str, Any]:
    """Simula um fluxo de frames para a demonstração do pipeline."""
    deteccoes_por_frame: list[list[dict[str, Any]]] = []
    total_deteccoes = 0
    for indice in range(frames_totais):
        deteccoes = detectar_imagem(f"{frame_path}_{indice}", num_deteccoes=random.randint(0, 2))
        frame_data = [{"classe_id": item.classe_id, "nome": item.nome, "confianca": item.confianca, "severidade": item.severidade} for item in deteccoes]
        deteccoes_por_frame.append(frame_data)
        total_deteccoes += len(frame_data)
    resumo: dict[str, int] = {}
    for frame in deteccoes_por_frame:
        for item in frame:
            resumo[item["nome"]] = resumo.get(item["nome"], 0) + 1
    return {"total_frames": frames_totais, "total_deteccoes": total_deteccoes, "deteccoes_por_frame": deteccoes_por_frame, "resumo_classes": resumo}
