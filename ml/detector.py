"""Detecção com YOLO: contagem de veículos e modelo de alagamento.

Os modelos só são carregados na primeira vez que forem usados, assim a API
funciona mesmo numa máquina sem os pesos. O modelo de veículos é o YOLO padrão
ajustado com imagens das câmeras da CET. O de alagamento foi treinado à parte.
"""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings

_RAIZ_PROJETO = Path(__file__).resolve().parents[1]


CLASSES_URBANAS = {
    # O projeto detecta só alagamento e trânsito. Os números das classes que
    # saíram do escopo não foram reaproveitados.
    1: {"nome": "alagamento", "severidade": "critica", "tipo": "alagamento"},
    2: {"nome": "transito", "severidade": "media", "tipo": "transito"},
    # Um veículo sozinho não é trânsito. Eles são contados juntos em
    # live_detection.py.
    8: {"nome": "veiculo", "severidade": "baixa", "tipo": "observacao_visual"},
    9: {"nome": "motocicleta", "severidade": "baixa", "tipo": "observacao_visual"},
    10: {"nome": "onibus", "severidade": "baixa", "tipo": "observacao_visual"},
    11: {"nome": "caminhao", "severidade": "baixa", "tipo": "observacao_visual"},
}

_URBANAS_POR_NOME = {meta["nome"]: (identificador, meta) for identificador, meta in CLASSES_URBANAS.items()}
_COCO_PARA_URBANO = {
    "car": "veiculo",
    "motorcycle": "motocicleta",
    "bus": "onibus",
    "truck": "caminhao",
}
_model: Any | None = None
_model_error: str | None = None

# O modelo de alagamento é separado do de veículos e tem pesos próprios.

_incident_model: Any | None = None
_incident_model_error: str | None = None


@dataclass
class Deteccao:
    """Uma detecção já no formato do sistema."""

    classe_id: int
    nome: str
    confianca: float
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int] = field(default_factory=lambda: (0, 0, 100, 100))
    classe_modelo: str | None = None


def _caminho_do_projeto(caminho: str) -> str:
    """Caminhos relativos partem da raiz do projeto, e não da pasta backend/."""
    p = Path(caminho)
    return str(p if p.is_absolute() else _RAIZ_PROJETO / p)


def _model_path() -> str:
    """Caminho do modelo de veículos."""
    return _caminho_do_projeto(settings.gx_yolo_model)


def _max_inferencias_simultaneas() -> int:
    """Quantas detecções podem rodar ao mesmo tempo.

    Sem esse limite as threads das câmeras rodavam o YOLO todas juntas e o
    servidor na nuvem ficava sem memória. O valor nunca fica abaixo de 1.
    """
    return max(1, settings.gx_yolo_max_concorrencia)


_inferencia_semaforo = threading.BoundedSemaphore(_max_inferencias_simultaneas())

# Garante que cada modelo seja carregado uma vez só, mesmo com várias threads
# pedindo ao mesmo tempo.
_carga_lock = threading.Lock()

# O YOLO dá erro quando duas threads usam o mesmo modelo ao mesmo tempo, então
# cada modelo tem a sua trava.
_model_infer_lock = threading.Lock()
_incident_infer_lock = threading.Lock()


def _imgsz() -> int:
    """Tamanho da imagem usado na detecção.

    É 1280 em vez do padrão 640 porque, com a imagem menor, o YOLO deixava de
    contar muitos carros pequenos ao fundo.
    """
    return max(320, settings.gx_yolo_imgsz)


def _tta() -> bool:
    """Diz se a contagem de veículos usa TTA.

    Com o TTA o YOLO também analisa a imagem espelhada e em outros tamanhos, o
    que encontrou um pouco mais de carros nos testes. Na nuvem fica desligado,
    porque deixa a detecção duas vezes mais lenta.
    """
    return settings.gx_yolo_tta


def _load_model() -> Any | None:
    """Carrega o modelo de veículos na primeira vez que ele for usado."""
    global _model, _model_error
    if _model is not None:
        return _model
    if _model_error is not None:
        return None

    with _carga_lock:
        # Se outra thread carregou o modelo enquanto esta esperava, usa o mesmo.
        if _model is not None or _model_error is not None:
            return _model
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
    """Diz se o modelo de veículos está disponível."""
    model = _load_model()
    return {
        "disponivel": model is not None,
        "modo": "yolo" if model is not None else "indisponivel",
        "modelo": _model_path(),
        "erro": _model_error,
        "mapeamento_padrao": dict(_COCO_PARA_URBANO),
        "aviso": "Pesos COCO padrão geram apenas observações de objetos. Alagamento, fumaça, incêndio e outros incidentes exigem pesos urbanos treinados e validação operacional.",
    }


def _incident_model_path() -> str:
    return _caminho_do_projeto(settings.gx_yolo_incident_model)


def _load_incident_model() -> Any | None:
    """Carrega o modelo de alagamento na primeira vez que ele for usado."""
    global _incident_model, _incident_model_error
    if _incident_model is not None:
        return _incident_model
    if _incident_model_error is not None:
        return None

    with _carga_lock:
        if _incident_model is not None or _incident_model_error is not None:
            return _incident_model
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
    """Diz se o modelo de alagamento está disponível."""
    model = _load_incident_model()
    return {
        "disponivel": model is not None,
        "modelo": _incident_model_path(),
        "erro": _incident_model_error,
    }


def detectar_incidentes_imagem(caminho_imagem: str, confianca_minima: float = 0.6) -> list[Deteccao]:
    """Procura alagamento na imagem com o modelo de alagamento."""
    model = _load_incident_model()
    if model is None:
        raise RuntimeError(_incident_model_error or "Detector de incidentes indisponível")

    resultados: list[Deteccao] = []
    # Primeiro espera a vez do modelo e só depois ocupa uma vaga do limite geral.
    with _incident_infer_lock, _inferencia_semaforo:
        predicoes = model.predict(source=caminho_imagem, conf=confianca_minima, verbose=False)
    for resultado in predicoes:
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
    nome = _COCO_PARA_URBANO.get(nome_modelo.lower().strip(), nome)
    return _URBANAS_POR_NOME.get(nome)


def detectar_imagem_real(caminho_imagem: str, confianca_minima: float = 0.45) -> list[Deteccao]:
    """Detecta os veículos da imagem e traduz as classes do YOLO para as do sistema."""
    model = _load_model()
    if model is None:
        raise RuntimeError(_model_error or "Detector YOLO indisponível")

    resultados: list[Deteccao] = []
    with _model_infer_lock, _inferencia_semaforo:
        predicoes = model.predict(source=caminho_imagem, conf=confianca_minima, imgsz=_imgsz(), augment=_tta(), verbose=False)
    for resultado in predicoes:
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
