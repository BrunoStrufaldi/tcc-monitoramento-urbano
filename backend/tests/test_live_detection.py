"""Testes do monitoramento de trânsito nas câmeras.

O download das imagens é simulado, sem acessar a internet.
"""

import time
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.services import detection_events, live_detection
from ml.detector import Deteccao


@contextmanager
def _sessao_de_teste(session: Session):
    yield session


def _veiculos(quantidade: int) -> list[Deteccao]:
    return [
        Deteccao(8, "veiculo", 0.8, "baixa", "observacao_visual", (i * 10, 0, i * 10 + 8, 8), "car")
        for i in range(quantidade)
    ]


@pytest.fixture(autouse=True)
def _sem_tomtom_por_padrao(monkeypatch):
    """Evita chamar a TomTom de verdade nos testes."""
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: {"disponivel": False})


def _monta_camera_transito(db_session, tmp_path, monkeypatch, veiculos: int, fluxo_tomtom: dict):
    monkeypatch.setattr(live_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(veiculos))
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: fluxo_tomtom)


def test_gatilho_de_tres_faixas_com_a_tomtom():
    """Contagem alta cria direto, contagem média depende da TomTom e contagem baixa precisa dela."""
    sem_tomtom = {"disponivel": False}
    casos = [
        # (veículos, resposta da TomTom, cria?, trecho do motivo)
        (16, sem_tomtom, True, "contagem alta"),
        (13, {"disponivel": True, "via_fechada": True, "indice_congestionamento": 0.0}, True, "fechada"),
        (13, sem_tomtom, True, "sem TomTom"),
        (13, {"disponivel": True, "indice_congestionamento": 5.0}, True, "confirma lentidão"),
        (13, {"disponivel": True, "indice_congestionamento": 1.5}, False, "fluindo"),
        (6, {"disponivel": True, "indice_congestionamento": 5.5}, True, "sustenta a contagem baixa"),
        (6, sem_tomtom, False, "nada a corroborar"),
        (6, {"disponivel": True, "indice_congestionamento": None}, False, "nada a corroborar"),
        (6, {"disponivel": True, "indice_congestionamento": 1.0}, False, "fluindo"),
    ]
    for veiculos, fluxo, esperado, trecho in casos:
        criar, motivo = live_detection._avaliar_gatilho_transito(veiculos, fluxo)
        assert criar is esperado, (veiculos, fluxo)
        assert trecho in motivo, (veiculos, fluxo)


def test_processar_frame_cria_transito_com_as_duas_fontes(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 6, {"disponivel": True, "indice_congestionamento": 8.0})

    cooldown: dict[str, float] = {}
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown)

    evento = db_session.query(Evento).one()
    assert evento.tipo == "transito"
    assert evento.titulo == "Possível Trânsito detectado pelo YOLO"
    assert evento.confianca is not None
    assert "transito" in cooldown

    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).all()
    chaves = {item.chave: float(item.valor_numerico) for item in contexto}
    assert chaves == {"indice_congestionamento": 3.0, "indice_congestionamento_tomtom": 8.0}


def test_processar_frame_veto_da_tomtom_nao_cria_e_espera_pouco(db_session: Session, tmp_path, monkeypatch):
    """Depois de uma recusa da TomTom a câmera espera pouco tempo, não meia hora."""
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 13, {"disponivel": True, "indice_congestionamento": 1.0})

    cooldown: dict[str, float] = {}
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown)

    assert db_session.query(Evento).count() == 0
    assert "transito" not in cooldown
    assert "transito_veto" in cooldown


def test_processar_frame_com_poucos_veiculos_nem_consulta_a_tomtom(db_session: Session, tmp_path, monkeypatch):
    consultas: list[int] = []

    def _tomtom(_lat, _lon):
        consultas.append(1)
        return {"disponivel": True, "indice_congestionamento": 9.0}

    _monta_camera_transito(db_session, tmp_path, monkeypatch, 3, {})
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", _tomtom)

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})

    assert db_session.query(Evento).count() == 0
    assert consultas == []


def test_processar_frame_nao_cria_em_espera_ou_sem_modelo(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 18, {"disponivel": False})
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {"transito": time.monotonic()})
    assert db_session.query(Evento).count() == 0

    def _falha(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(live_detection, "detectar_imagem_real", _falha)
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})
    assert db_session.query(Evento).count() == 0


def test_loop_ignora_frame_desatualizado_e_nao_processa(monkeypatch):
    """Câmera travada mandando sempre a mesma foto antiga: a imagem é ignorada."""
    import httpx as httpx_module

    class _RespostaFalsa:
        def __init__(self) -> None:
            self.content = b"frame-fake"
            self.headers = httpx_module.Headers({"last-modified": "Wed, 25 Feb 2026 12:02:13 GMT"})

        def raise_for_status(self) -> None:
            return None

    class _ClienteFalso:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> bool:
            return False

        def get(self, _url):
            return _RespostaFalsa()

    monkeypatch.setattr(httpx_module, "Client", _ClienteFalso)
    chamadas: list[int] = []
    monkeypatch.setattr(live_detection, "_processar_frame", lambda *_a, **_k: chamadas.append(1))

    live_detection._stop_event.clear()
    monkeypatch.setattr(live_detection._stop_event, "wait", lambda _segundos: live_detection._stop_event.set())

    live_detection._loop("http://fake/1.jpg", -23.55, -46.63, 1.0, 0.45, "câmera teste")

    assert chamadas == []


def test_iniciar_sobe_uma_thread_por_camera_so_quando_ligado(monkeypatch):
    from app.config import settings
    from app.services import cet_camera_catalog

    monkeypatch.setattr(settings, "gx_camera_snapshot_url", None)
    monkeypatch.setattr(settings, "gx_transito_monitorar_catalogo", False)
    live_detection.iniciar()
    assert live_detection._threads == []

    monkeypatch.setattr(settings, "gx_transito_monitorar_catalogo", True)
    # Troca o loop real, que acessaria as câmeras, por um que só espera o sinal de parada.
    monkeypatch.setattr(live_detection, "_loop", lambda *_args: live_detection._stop_event.wait())
    try:
        live_detection.iniciar()
        assert len(live_detection._threads) == len(cet_camera_catalog.CAMERAS)
        assert all(thread.is_alive() for thread in live_detection._threads)
    finally:
        live_detection.parar()
