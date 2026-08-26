"""Testes do monitoramento automático de ocorrências GeoSampa/Defesa Civil —
dedup por identificador externo, corroboração com clima via Data Fusion, e
confirmação (status + Notificacao) só acima do limiar de confiabilidade."""

from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.services import context_monitor


@contextmanager
def _sessao_de_teste(session: Session):
    yield session


@pytest.fixture(autouse=True)
def _sem_corroboracao_visual_por_padrao(monkeypatch):
    """A maioria dos testes aqui não é sobre a câmera — evita rede/YOLO real."""
    monkeypatch.setattr(context_monitor, "status_detector", lambda: {"disponivel": False})


def _ocorrencia(identificador: str = "123") -> dict:
    return {
        "identificador": identificador,
        "latitude": -23.55,
        "longitude": -46.63,
        "data_ocorrencia": "2026-06-01",
        "subprefeitura": "SE - SE",
    }


def _ocorrencia_acidente(identificador: str = "900", *, feridos: int = 0, fatais: int = 0) -> dict:
    return {
        "identificador": identificador,
        "latitude": -23.55,
        "longitude": -46.63,
        "data_ocorrencia": "2026-06-01",
        "logradouro": "Av. Paulista",
        "tipo_acidente": "Colisão traseira",
        "feridos": feridos,
        "fatais": fatais,
    }


def test_processar_ocorrencia_nova_cria_evento_em_analise(db_session: Session, monkeypatch):
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 32.0, "vento_kmh": 5.0},
    )

    from app.models.evento import Evento
    from app.models.notificacao import Notificacao
    from app.models.ocorrencia_externa import OcorrenciaExterna

    context_monitor._processar_ocorrencia(db_session, "geosampa_alagamento", _ocorrencia("111"))

    eventos = db_session.query(Evento).all()
    assert len(eventos) == 1
    assert eventos[0].tipo == "alagamento"
    assert eventos[0].fonte.nome == "Defesa Civil (GeoSampa)"

    rastreio = db_session.query(OcorrenciaExterna).filter(OcorrenciaExterna.identificador_externo == "111").first()
    assert rastreio is not None
    assert rastreio.evento_id == eventos[0].id

    # fonte oficial (0.92) + chuva forte corroborando -> passa do limiar padrão (0.75)
    assert eventos[0].status == "ativo"
    assert db_session.query(Notificacao).filter(Notificacao.evento_id == eventos[0].id).count() == 1


def test_processar_ocorrencia_abaixo_do_limiar_nao_confirma(db_session: Session, monkeypatch):
    monkeypatch.setattr(context_monitor.settings, "gx_confirmacao_confianca_minima", 0.99)
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 32.0, "vento_kmh": 5.0},
    )

    from app.models.evento import Evento
    from app.models.notificacao import Notificacao

    context_monitor._processar_ocorrencia(db_session, "geosampa_alagamento", _ocorrencia("222"))

    evento = db_session.query(Evento).first()
    assert evento.status == "em_analise"
    assert db_session.query(Notificacao).filter(Notificacao.evento_id == evento.id).count() == 0


def test_processar_ocorrencia_ja_vista_nao_duplica(db_session: Session, monkeypatch):
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 32.0, "vento_kmh": 5.0},
    )

    from app.models.evento import Evento

    context_monitor._processar_ocorrencia(db_session, "geosampa_alagamento", _ocorrencia("333"))
    context_monitor._processar_ocorrencia(db_session, "geosampa_alagamento", _ocorrencia("333"))

    assert db_session.query(Evento).count() == 1


def test_processar_ocorrencia_sem_clima_disponivel_ainda_funciona(db_session: Session, monkeypatch):
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": False, "erro": "timeout"},
    )

    from app.models.dado_contextual import DadoContextual
    from app.models.evento import Evento

    context_monitor._processar_ocorrencia(db_session, "geosampa_queda_arvore", _ocorrencia("444"))

    evento = db_session.query(Evento).first()
    assert evento is not None
    assert evento.tipo == "arvore_caida"
    assert db_session.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).count() == 0


def test_checar_geosampa_processa_apenas_ocorrencias_novas(db_session: Session, monkeypatch):
    monkeypatch.setattr(context_monitor, "SessionLocal", lambda: _sessao_de_teste(db_session))
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 5.0, "vento_kmh": 5.0},
    )
    monkeypatch.setattr(context_monitor.geosampa_source, "buscar_alagamentos", lambda _data: [_ocorrencia("555"), _ocorrencia("556")])
    monkeypatch.setattr(context_monitor.geosampa_source, "buscar_quedas_de_arvore", lambda _data: [])
    monkeypatch.setattr(context_monitor.geosampa_source, "buscar_acidentes_transito", lambda _data: [])

    from app.models.evento import Evento

    context_monitor._checar_geosampa()
    assert db_session.query(Evento).count() == 2

    context_monitor._checar_geosampa()
    assert db_session.query(Evento).count() == 2


def test_processar_ocorrencia_acidente_transito_usa_fonte_cet(db_session: Session, monkeypatch):
    monkeypatch.setattr(
        context_monitor,
        "obter_condicoes_atuais",
        lambda _lat, _lon: {"disponivel": True, "chuva_mm": 0.0, "vento_kmh": 5.0},
    )

    from app.models.evento import Evento

    context_monitor._processar_ocorrencia(db_session, "geosampa_acidente_transito", _ocorrencia_acidente("901"))

    evento = db_session.query(Evento).first()
    assert evento.tipo == "acidente_transito"
    assert evento.fonte.nome == "CET (GeoSampa)"
    assert "Av. Paulista" in evento.descricao


@pytest.mark.parametrize(
    ("feridos", "fatais", "severidade_esperada"),
    [(0, 0, "media"), (2, 0, "alta"), (1, 1, "critica")],
)
def test_severidade_acidente_por_feridos_e_fatais(feridos, fatais, severidade_esperada):
    ocorrencia = _ocorrencia_acidente(feridos=feridos, fatais=fatais)
    assert context_monitor._severidade_acidente(ocorrencia) == severidade_esperada


class _RespostaFalsa:
    def __init__(self, conteudo: bytes = b"jpg-fake"):
        self.content = conteudo

    def raise_for_status(self) -> None:
        return None


def _criar_localizacao(db: Session, latitude: float, longitude: float) -> int:
    from app.models.localizacao import Localizacao

    localizacao = Localizacao(latitude=latitude, longitude=longitude)
    db.add(localizacao)
    db.commit()
    return localizacao.id


def test_buscar_corroboracao_visual_sem_camera_por_perto(db_session: Session, monkeypatch):
    from app.models.evento import Evento
    from app.models.evidencia_visual import EvidenciaVisual

    evento = Evento(titulo="t", tipo="alagamento", severidade="alta", status="em_analise", localizacao_id=_criar_localizacao(db_session, -23.9, -47.5))
    db_session.add(evento)
    db_session.commit()

    monkeypatch.setattr(context_monitor, "status_detector", lambda: {"disponivel": True})
    monkeypatch.setattr(context_monitor, "status_incident_detector", lambda: {"disponivel": False})
    context_monitor._buscar_corroboracao_visual(db_session, evento.id, -23.9, -47.5, "alagamento")

    assert db_session.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id == evento.id).count() == 0


def test_buscar_corroboracao_visual_com_camera_registra_sinal_limitado(db_session: Session, monkeypatch):
    from app.models.evento import Evento
    from app.models.evidencia_visual import EvidenciaVisual
    from app.services.cet_camera_catalog import CAMERAS
    from ml.detector import Deteccao

    referencia = CAMERAS[0]
    evento = Evento(titulo="t", tipo="arvore_caida", severidade="media", status="em_analise", localizacao_id=_criar_localizacao(db_session, referencia.latitude, referencia.longitude))
    db_session.add(evento)
    db_session.commit()

    monkeypatch.setattr(context_monitor, "status_detector", lambda: {"disponivel": True})
    monkeypatch.setattr(context_monitor, "status_incident_detector", lambda: {"disponivel": False})
    monkeypatch.setattr(context_monitor.httpx, "get", lambda *a, **k: _RespostaFalsa())
    monkeypatch.setattr(
        context_monitor,
        "detectar_imagem_real",
        lambda _path, _threshold: [Deteccao(8, "veiculo", 0.95, "baixa", "observacao_visual", (0, 0, 10, 10), "car")],
    )

    context_monitor._buscar_corroboracao_visual(db_session, evento.id, referencia.latitude, referencia.longitude, "arvore_caida")
    db_session.flush()

    evidencia = db_session.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id == evento.id).first()
    assert evidencia is not None
    assert evidencia.confianca < 0.95  # sinal limitado, não a confiança bruta do YOLO
    assert evidencia.metadados["sinal_indireto"] is True
    assert evidencia.metadados["camera_id"] == referencia.id


def test_buscar_corroboracao_visual_com_modelo_de_incidentes_confirma_direto(db_session: Session, monkeypatch):
    from app.models.evento import Evento
    from app.models.evidencia_visual import EvidenciaVisual
    from app.services.cet_camera_catalog import CAMERAS
    from ml.detector import Deteccao

    referencia = CAMERAS[0]
    evento = Evento(titulo="t", tipo="arvore_caida", severidade="media", status="em_analise", localizacao_id=_criar_localizacao(db_session, referencia.latitude, referencia.longitude))
    db_session.add(evento)
    db_session.commit()

    monkeypatch.setattr(context_monitor, "status_incident_detector", lambda: {"disponivel": True})
    monkeypatch.setattr(context_monitor.httpx, "get", lambda *a, **k: _RespostaFalsa())
    monkeypatch.setattr(
        context_monitor,
        "detectar_incidentes_imagem",
        lambda _path, _threshold: [Deteccao(6, "arvore_caida", 0.88, "media", "infraestrutura", (0, 0, 10, 10), "fallen tree")],
    )

    context_monitor._buscar_corroboracao_visual(db_session, evento.id, referencia.latitude, referencia.longitude, "arvore_caida")
    db_session.flush()

    evidencia = db_session.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id == evento.id).first()
    assert evidencia is not None
    assert float(evidencia.confianca) == 0.88  # confirmação direta, sem teto de sinal indireto
    assert evidencia.metadados["sinal_indireto"] is False


def test_buscar_corroboracao_visual_falha_de_rede_nao_propaga(db_session: Session, monkeypatch):
    import httpx as httpx_module

    from app.models.evento import Evento
    from app.models.evidencia_visual import EvidenciaVisual
    from app.services.cet_camera_catalog import CAMERAS

    referencia = CAMERAS[0]
    evento = Evento(titulo="t", tipo="arvore_caida", severidade="media", status="em_analise", localizacao_id=_criar_localizacao(db_session, referencia.latitude, referencia.longitude))
    db_session.add(evento)
    db_session.commit()

    def _falha(*_a, **_k):
        raise httpx_module.ConnectError("sem rede")

    monkeypatch.setattr(context_monitor, "status_detector", lambda: {"disponivel": True})
    monkeypatch.setattr(context_monitor, "status_incident_detector", lambda: {"disponivel": False})
    monkeypatch.setattr(context_monitor.httpx, "get", _falha)

    context_monitor._buscar_corroboracao_visual(db_session, evento.id, referencia.latitude, referencia.longitude, "arvore_caida")

    assert db_session.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id == evento.id).count() == 0
