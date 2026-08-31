"""Testes da detecção contínua (câmera IP/RTSP) — cobre o processamento de
frame, a contagem de veículos para sinalizar trânsito, o cooldown e o filtro
de frame desatualizado (``_loop``, HTTP mockado); download HTTP de verdade
não é exercitado aqui."""

from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

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
    """A maioria dos testes aqui não é sobre o TomTom — evita rede real."""
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: {"disponivel": False})


def test_processar_frame_ignora_poucos_veiculos(db_session: Session, monkeypatch):
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(3))

    from app.models.evento import Evento

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})
    assert db_session.query(Evento).count() == 0


def test_processar_frame_sinaliza_transito_acima_do_limite(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(live_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(live_detection.settings, "gx_transito_min_veiculos", 5)
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(6))

    cooldown: dict[str, float] = {}
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown)

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    eventos = db_session.query(Evento).all()
    assert len(eventos) == 1
    assert eventos[0].tipo == "transito"
    assert eventos[0].titulo == "Possível Trânsito detectado pelo YOLO"
    assert eventos[0].confianca is not None
    assert "transito" in cooldown

    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == eventos[0].id).all()
    assert len(contexto) == 1
    assert contexto[0].chave == "indice_congestionamento"
    assert contexto[0].valor_numerico == 3.0


def test_processar_frame_com_tomtom_disponivel_registra_duas_fontes(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(live_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(live_detection.settings, "gx_transito_min_veiculos", 5)
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(6))
    monkeypatch.setattr(
        live_detection,
        "obter_fluxo_transito",
        lambda _lat, _lon: {"disponivel": True, "indice_congestionamento": 8.0},
    )

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).all()
    chaves = {item.chave: float(item.valor_numerico) for item in contexto}
    assert chaves == {"indice_congestionamento": 3.0, "indice_congestionamento_tomtom": 8.0}


def test_avaliar_gatilho_contagem_alta_cria_sem_tomtom():
    criar, motivo = live_detection._avaliar_gatilho_transito(16, {"disponivel": False})
    assert criar is True
    assert "contagem alta" in motivo


def test_avaliar_gatilho_via_fechada_cria():
    criar, motivo = live_detection._avaliar_gatilho_transito(
        13, {"disponivel": True, "via_fechada": True, "indice_congestionamento": 0.0}
    )
    assert criar is True
    assert "fechada" in motivo


def test_avaliar_gatilho_sem_tomtom_cai_na_contagem():
    criar, motivo = live_detection._avaliar_gatilho_transito(13, {"disponivel": False})
    assert criar is True
    assert "sem TomTom" in motivo


def test_avaliar_gatilho_tomtom_confirma_lentidao():
    criar, motivo = live_detection._avaliar_gatilho_transito(
        13, {"disponivel": True, "indice_congestionamento": 5.0}
    )
    assert criar is True
    assert "confirma lentidão" in motivo


def test_avaliar_gatilho_tomtom_veta_trecho_fluindo():
    criar, motivo = live_detection._avaliar_gatilho_transito(
        13, {"disponivel": True, "indice_congestionamento": 1.5}
    )
    assert criar is False
    assert "fluindo" in motivo


def _monta_camera_transito(db_session, tmp_path, monkeypatch, veiculos: int, fluxo_tomtom: dict):
    monkeypatch.setattr(live_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(veiculos))
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: fluxo_tomtom)


def test_processar_frame_veta_transito_quando_tomtom_indica_fluxo(db_session: Session, tmp_path, monkeypatch):
    # 13 veículos (faixa intermediária) mas a TomTom diz que o trecho flui —
    # provável contagem dos dois sentidos numa avenida larga. Não vira evento.
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 13, {"disponivel": True, "indice_congestionamento": 1.0})

    from app.models.evento import Evento

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})
    assert db_session.query(Evento).count() == 0


def test_processar_frame_cria_transito_quando_tomtom_confirma(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 13, {"disponivel": True, "indice_congestionamento": 6.0})

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})

    evento = db_session.query(Evento).one()
    assert evento.tipo == "transito"
    chaves = {c.chave for c in db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id)}
    assert chaves == {"indice_congestionamento", "indice_congestionamento_tomtom"}


def test_processar_frame_contagem_alta_cria_mesmo_com_tomtom_baixo(db_session: Session, tmp_path, monkeypatch):
    # 18 >= gx_transito_min_veiculos_confirmado (16): frame muito cheio dispensa
    # a corroboração da TomTom.
    _monta_camera_transito(db_session, tmp_path, monkeypatch, 18, {"disponivel": True, "indice_congestionamento": 1.0})

    from app.models.evento import Evento

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})
    assert db_session.query(Evento).count() == 1


def test_processar_frame_respeita_cooldown_de_transito(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(live_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(live_detection.settings, "gx_transito_min_veiculos", 5)
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _path, _threshold: _veiculos(6))

    import time

    cooldown = {"transito": time.monotonic()}
    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown)

    from app.models.evento import Evento

    assert db_session.query(Evento).count() == 0


def test_processar_frame_ignora_quando_modelo_indisponivel(db_session: Session, monkeypatch):
    def _falha(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(live_detection, "detectar_imagem_real", _falha)

    from app.models.evento import Evento

    live_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {})
    assert db_session.query(Evento).count() == 0


def test_loop_ignora_frame_desatualizado_e_nao_processa(monkeypatch):
    """Caso real que motivou o filtro: câmera CET travada, sempre devolvendo
    o mesmo JPEG de meses atrás — precisa ser descartado antes de virar
    Deteccao, senão vira evento "ao vivo" com foto de outra hora do dia."""
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


def test_iniciar_sem_snapshot_url_nao_sobe_thread(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gx_camera_snapshot_url", None)
    monkeypatch.setattr(settings, "gx_transito_monitorar_catalogo", False)
    live_detection.iniciar()
    assert live_detection._threads == []


def test_iniciar_com_catalogo_ativo_sobe_uma_thread_por_camera(monkeypatch):
    from app.config import settings
    from app.services import cet_camera_catalog

    monkeypatch.setattr(settings, "gx_camera_snapshot_url", None)
    monkeypatch.setattr(settings, "gx_transito_monitorar_catalogo", True)
    # Substitui o loop real (que faria HTTP GET nas câmeras da CET-SP de
    # verdade) por um stub que só aguarda o sinal de parada.
    monkeypatch.setattr(live_detection, "_loop", lambda *_args: live_detection._stop_event.wait())
    try:
        live_detection.iniciar()
        assert len(live_detection._threads) == len(cet_camera_catalog.CAMERAS)
        assert all(thread.is_alive() for thread in live_detection._threads)
    finally:
        live_detection.parar()
