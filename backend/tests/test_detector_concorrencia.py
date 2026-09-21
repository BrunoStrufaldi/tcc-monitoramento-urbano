"""Garantias de concorrência de ml/detector.py.

Motivação (Cloud Run, 20/09/2026): com o catálogo ligado, 20 threads chamam o
YOLO ao mesmo tempo. Sem trava, cada uma carregava sua própria cópia do peso;
sem semáforo, todas inferiam juntas. Em CPU com 4 GiB o container morria por
OOM 19 s depois de carregar o modelo, levando o SQLite junto.
"""

import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml import detector  # noqa: E402


class _ModeloLento:
    """Simula um peso carregado: predict segura o semáforo por um instante e
    registra quantas chamadas estão vivas ao mesmo tempo."""

    def __init__(self) -> None:
        self.ativas = 0
        self.pico = 0
        self._lock = threading.Lock()

    def predict(self, **_kwargs):
        with self._lock:
            self.ativas += 1
            self.pico = max(self.pico, self.ativas)
        threading.Event().wait(0.02)
        with self._lock:
            self.ativas -= 1
        return []


@pytest.fixture
def detector_limpo(monkeypatch):
    """Zera o estado global do módulo e substitui o construtor YOLO por um
    contador, para o teste não depender de peso nem de ultralytics."""
    cargas = {"n": 0}
    modelo = _ModeloLento()

    def _yolo_falso(_caminho):
        cargas["n"] += 1
        threading.Event().wait(0.05)  # janela em que as outras threads chegam
        return modelo

    import types

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=_yolo_falso))
    monkeypatch.setattr(detector, "_model", None)
    monkeypatch.setattr(detector, "_model_error", None)
    monkeypatch.setattr(detector, "_incident_model", None)
    monkeypatch.setattr(detector, "_incident_model_error", None)
    monkeypatch.setattr(detector.Path, "is_file", lambda _self: True)
    return cargas, modelo


def _disparar(alvo, n: int) -> None:
    threads = [threading.Thread(target=alvo) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)


def test_peso_e_carregado_uma_unica_vez_sob_concorrencia(detector_limpo):
    cargas, _ = detector_limpo
    _disparar(detector._load_model, 20)
    assert cargas["n"] == 1


def test_peso_de_incidentes_tambem_carrega_uma_vez(detector_limpo):
    cargas, _ = detector_limpo
    _disparar(detector._load_incident_model, 20)
    assert cargas["n"] == 1


def test_inferencias_simultaneas_respeitam_o_semaforo(detector_limpo, monkeypatch):
    _, modelo = detector_limpo
    monkeypatch.setattr(detector, "_inferencia_semaforo", threading.BoundedSemaphore(2))

    _disparar(lambda: detector.detectar_imagem_real("qualquer.jpg"), 20)
    assert modelo.pico <= 2

    _disparar(lambda: detector.detectar_incidentes_imagem("qualquer.jpg"), 20)
    assert modelo.pico <= 2


def test_limite_de_concorrencia_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("GX_YOLO_MAX_CONCORRENCIA", "3")
    assert detector._max_inferencias_simultaneas() == 3
    monkeypatch.setenv("GX_YOLO_MAX_CONCORRENCIA", "0")
    assert detector._max_inferencias_simultaneas() == 1  # nunca zero: travaria tudo
    monkeypatch.setenv("GX_YOLO_MAX_CONCORRENCIA", "abc")
    assert detector._max_inferencias_simultaneas() == 2
