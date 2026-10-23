"""Testes de concorrência do ml/detector.py.

Com várias câmeras ligadas, muitas threads chamam o YOLO ao mesmo tempo. Sem os
limites do detector, o servidor na nuvem ficava sem memória.
"""

import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402
from ml import detector  # noqa: E402


class _ModeloLento:
    """Modelo falso que conta quantas detecções estão rodando ao mesmo tempo."""

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
    """Limpa o estado do detector e troca o YOLO por um modelo falso."""
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


def test_cada_peso_e_carregado_uma_unica_vez(detector_limpo):
    cargas, _ = detector_limpo
    _disparar(detector._load_model, 20)
    _disparar(detector._load_incident_model, 20)
    assert cargas["n"] == 2


def test_inferencia_respeita_o_semaforo_e_a_trava_de_cada_modelo(detector_limpo, monkeypatch):
    """Duas threads nunca usam o mesmo modelo juntas, mas trânsito e alagamento seguem em paralelo."""
    _, modelo = detector_limpo
    monkeypatch.setattr(detector, "_inferencia_semaforo", threading.BoundedSemaphore(2))

    _disparar(lambda: detector.detectar_imagem_real("qualquer.jpg"), 20)
    assert modelo.pico == 1

    modelo.pico = 0
    _disparar(lambda: detector.detectar_incidentes_imagem("qualquer.jpg"), 20)
    assert modelo.pico == 1

    modelo.pico = 0
    alvos = [lambda: detector.detectar_imagem_real("a.jpg"), lambda: detector.detectar_incidentes_imagem("b.jpg")] * 10
    threads = [threading.Thread(target=alvo) for alvo in alvos]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert modelo.pico <= 2


def test_configuracao_do_yolo_vem_do_settings(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(settings, "gx_yolo_max_concorrencia", 3)
    assert detector._max_inferencias_simultaneas() == 3
    monkeypatch.setattr(settings, "gx_yolo_max_concorrencia", 0)
    assert detector._max_inferencias_simultaneas() == 1  # nunca zero: travaria tudo

    # Caminhos relativos dos modelos partem da raiz do projeto, não de backend/.
    monkeypatch.setattr(settings, "gx_yolo_incident_model", "ml/models/gx-incident.pt")
    assert Path(detector._incident_model_path()) == PROJECT_ROOT / "ml" / "models" / "gx-incident.pt"
    absoluto = str(PROJECT_ROOT / "outro.pt")
    monkeypatch.setattr(settings, "gx_yolo_model", absoluto)
    assert detector._model_path() == absoluto

    monkeypatch.setenv("GX_YOLO_IMGSZ", "960")
    monkeypatch.setenv("GX_YOLO_TTA", "false")
    lido = Settings()
    assert lido.gx_yolo_imgsz == 960
    assert lido.gx_yolo_tta is False
