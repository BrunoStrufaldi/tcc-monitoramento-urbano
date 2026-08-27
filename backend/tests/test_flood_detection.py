"""Testes da detecção contínua de alagamento (câmera CET) — processamento de
frame, correção de Evento.tipo, cooldown e o filtro de frame desatualizado
(``_loop``, HTTP mockado); download HTTP de verdade não é exercitado aqui."""

from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.services import detection_events, flood_detection
from ml.detector import Deteccao


@contextmanager
def _sessao_de_teste(session: Session):
    yield session


@pytest.fixture(autouse=True)
def _sem_clima_por_padrao(monkeypatch):
    """A maioria dos testes aqui não é sobre chuva/aviso oficial — evita rede
    real (Open-Meteo, INMET)."""
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False})


def _deteccao_alagamento(confianca: float = 0.8) -> list[Deteccao]:
    # Deteccao.tipo vem como a categoria ampla ("clima"), não "alagamento" —
    # mesmo formato que detectar_incidentes_imagem devolve de verdade.
    return [Deteccao(1, "alagamento", confianca, "critica", "clima", (0, 0, 50, 50), "flood")]


def test_processar_frame_ignora_quando_nao_detecta_alagamento(db_session: Session, monkeypatch):
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: [])

    from app.models.evento import Evento

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")
    assert db_session.query(Evento).count() == 0


def test_processar_frame_sinaliza_alagamento_com_tipo_corrigido(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento(0.81))

    cooldown: dict[str, float] = {}
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown, "câmera teste")

    from app.models.evento import Evento

    eventos = db_session.query(Evento).all()
    assert len(eventos) == 1
    # CLASSES_URBANAS guarda "clima" como categoria de alagamento — o evento
    # tem que virar o tipo específico, senão data_fusion.scores não reconhece.
    assert eventos[0].tipo == "alagamento"
    assert float(eventos[0].confianca) == 0.81
    assert "câmera teste" in eventos[0].fonte.nome
    assert "alagamento" in cooldown


def test_processar_frame_com_chuva_disponivel_registra_contexto_climatico(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())
    monkeypatch.setattr(
        flood_detection,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 18.5},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).all()
    assert len(contexto) == 1
    assert contexto[0].categoria == "clima"
    assert contexto[0].chave == "precipitacao_mm_h"
    assert float(contexto[0].valor_numerico) == 18.5


def test_processar_frame_sem_chuva_disponivel_nao_registra_contexto(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())
    # fixture autouse já cobre "disponivel": False; aqui é o caso "disponivel"
    # mas sem o campo de chuva, defensivo contra resposta parcial da API.
    monkeypatch.setattr(
        flood_detection,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": None},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    assert db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).count() == 0


def test_processar_frame_com_aviso_inmet_de_alagamento_registra_contexto(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": True, "severidade_indice": 7.0, "severidade": "Perigo"},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).all()
    assert len(contexto) == 1
    assert contexto[0].chave == "alerta_inmet_severidade"
    assert float(contexto[0].valor_numerico) == 7.0


def test_processar_frame_com_aviso_inmet_sem_mencao_a_alagamento_nao_registra(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())
    # Aviso ativo existe, mas não fala de alagamento (ex.: só vento) — não
    # deve virar corroboração de um evento de alagamento.
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": False, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    assert db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).count() == 0


def test_processar_frame_combina_chuva_e_aviso_inmet(db_session: Session, tmp_path, monkeypatch):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": True, "chuva_mm": 22.0})
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": True, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    evento = db_session.query(Evento).first()
    contexto = db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).all()
    chaves = {item.chave: float(item.valor_numerico) for item in contexto}
    assert chaves == {"precipitacao_mm_h": 22.0, "alerta_inmet_severidade": 9.5}


def test_processar_frame_respeita_cooldown(db_session: Session, monkeypatch):
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento())

    import time

    from app.models.evento import Evento

    cooldown = {"alagamento": time.monotonic()}
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown, "câmera teste")
    assert db_session.query(Evento).count() == 0


def test_processar_frame_ignora_quando_modelo_indisponivel(db_session: Session, monkeypatch):
    def _falha(_path, _threshold):
        raise RuntimeError("modelo de incidentes indisponível")

    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", _falha)

    from app.models.evento import Evento

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")
    assert db_session.query(Evento).count() == 0


def test_loop_ignora_frame_desatualizado_e_nao_processa(monkeypatch):
    """Mesmo bug real da câmera 22 achado no trânsito: sem o filtro, um frame
    de meses atrás vira evento "ao vivo" de alagamento também."""
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
    monkeypatch.setattr(flood_detection, "_processar_frame", lambda *_a, **_k: chamadas.append(1))

    flood_detection._stop_event.clear()
    monkeypatch.setattr(flood_detection._stop_event, "wait", lambda _segundos: flood_detection._stop_event.set())

    flood_detection._loop("http://fake/1.jpg", -23.55, -46.63, 1.0, 0.45, "câmera teste")

    assert chamadas == []


def test_iniciar_desligado_por_padrao_nao_sobe_thread(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gx_alagamento_monitorar_catalogo", False)
    flood_detection.iniciar()
    assert flood_detection._threads == []


def test_iniciar_ativo_sobe_uma_thread_por_camera(monkeypatch):
    from app.config import settings
    from app.services import cet_camera_catalog

    monkeypatch.setattr(settings, "gx_alagamento_monitorar_catalogo", True)
    # Substitui o loop real (que faria HTTP GET nas câmeras da CET-SP de
    # verdade) por um stub que só aguarda o sinal de parada.
    monkeypatch.setattr(flood_detection, "_loop", lambda *_args: flood_detection._stop_event.wait())
    try:
        flood_detection.iniciar()
        assert len(flood_detection._threads) == len(cet_camera_catalog.CAMERAS)
        assert all(thread.is_alive() for thread in flood_detection._threads)
    finally:
        flood_detection.parar()
