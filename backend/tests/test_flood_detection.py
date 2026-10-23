"""Testes do monitoramento de alagamento nas câmeras.

O download das imagens é simulado, sem acessar a internet.
"""

import time
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.services import detection_events, flood_detection
from ml.detector import Deteccao


@contextmanager
def _sessao_de_teste(session: Session):
    yield session


@pytest.fixture(autouse=True)
def _sem_clima_por_padrao(monkeypatch):
    """Evita chamar o Open-Meteo e o INMET de verdade e zera o histórico da via."""
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "indice_historico", lambda _lat, _lon: (0.0, "sem histórico (fixture de teste)"))


def _deteccao_alagamento(confianca: float = 0.8) -> list[Deteccao]:
    # Mesmo formato que detectar_incidentes_imagem devolve de verdade.
    return [Deteccao(1, "alagamento", confianca, "critica", "alagamento", (0, 0, 50, 50), "flood")]


def _monta_camera_alagamento(db_session, tmp_path, monkeypatch, confianca: float = 0.8):
    monkeypatch.setattr(flood_detection, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 10, 10))
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: _deteccao_alagamento(confianca))


def _contexto_do_evento(db_session) -> dict[str, DadoContextual]:
    evento = db_session.query(Evento).one()
    return {d.chave: d for d in db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id)}


def test_processar_frame_sem_contexto_cria_evento_em_analise(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_alagamento(db_session, tmp_path, monkeypatch, 0.81)

    cooldown: dict[str, float] = {}
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, cooldown, "câmera teste")

    evento = db_session.query(Evento).one()
    # Evento.tipo é o que data_fusion.scores usa para escolher o cálculo.
    assert evento.tipo == "alagamento"
    # A confiança salva é a do Data Fusion, não a do YOLO. Sem chuva, sem aviso
    # e sem histórico, a nota cai e o evento fica em análise.
    assert float(evento.confianca) == 0.57
    assert evento.status == "em_analise"
    assert "câmera teste" in evento.fonte.nome
    assert "alagamento" in cooldown


def test_processar_frame_registra_chuva_aviso_e_historico(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_alagamento(db_session, tmp_path, monkeypatch)
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": True, "chuva_mm": 22.0})
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": True, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )
    # A coordenada cai num ponto que alaga sempre.
    monkeypatch.setattr(flood_detection, "indice_historico", lambda _lat, _lon: (8.5, "Av. Exemplo (~80 m, recorrência cronico)"))

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    contexto = _contexto_do_evento(db_session)
    valores = {chave: float(d.valor_numerico) for chave, d in contexto.items()}
    assert valores == {"precipitacao_mm_h": 22.0, "alerta_inmet_severidade": 9.5, "historico_alagamento_indice": 8.5}
    assert all(d.categoria == "contexto" for d in contexto.values())
    assert contexto["historico_alagamento_indice"].unidade == "indice_0_10"


def test_processar_frame_descarta_contexto_incompleto(db_session: Session, tmp_path, monkeypatch):
    """A API do clima responde sem o dado de chuva e o aviso do INMET não fala de alagamento."""
    _monta_camera_alagamento(db_session, tmp_path, monkeypatch)
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": True, "chuva_mm": None})
    monkeypatch.setattr(
        flood_detection,
        "obter_aviso_ativo",
        lambda: {"disponivel": True, "menciona_alagamento": False, "severidade_indice": 9.5, "severidade": "Grande Perigo"},
    )

    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    contexto = _contexto_do_evento(db_session)
    assert "precipitacao_mm_h" not in contexto
    assert "alerta_inmet_severidade" not in contexto


def test_processar_frame_nao_cria_sem_alagamento_em_espera_ou_sem_modelo(db_session: Session, tmp_path, monkeypatch):
    _monta_camera_alagamento(db_session, tmp_path, monkeypatch)
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {"alagamento": time.monotonic()}, "câmera teste")

    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _path, _threshold: [])
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

    def _falha(_path, _threshold):
        raise RuntimeError("modelo de incidentes indisponível")

    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", _falha)
    flood_detection._processar_frame(b"frame-fake", -23.55, -46.63, 0.45, {}, "câmera teste")

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
    monkeypatch.setattr(flood_detection, "_processar_frame", lambda *_a, **_k: chamadas.append(1))

    flood_detection._stop_event.clear()
    monkeypatch.setattr(flood_detection._stop_event, "wait", lambda _segundos: flood_detection._stop_event.set())

    flood_detection._loop("http://fake/1.jpg", -23.55, -46.63, 1.0, 0.45, "câmera teste")

    assert chamadas == []


def test_iniciar_sobe_uma_thread_por_camera_so_quando_ligado(monkeypatch):
    from app.config import settings
    from app.services import cet_camera_catalog

    monkeypatch.setattr(settings, "gx_alagamento_monitorar_catalogo", False)
    flood_detection.iniciar()
    assert flood_detection._threads == []

    monkeypatch.setattr(settings, "gx_alagamento_monitorar_catalogo", True)
    # Troca o loop real, que acessaria as câmeras, por um que só espera o sinal de parada.
    monkeypatch.setattr(flood_detection, "_loop", lambda *_args: flood_detection._stop_event.wait())
    try:
        flood_detection.iniciar()
        assert len(flood_detection._threads) == len(cet_camera_catalog.CAMERAS)
        assert all(thread.is_alive() for thread in flood_detection._threads)
    finally:
        flood_detection.parar()
