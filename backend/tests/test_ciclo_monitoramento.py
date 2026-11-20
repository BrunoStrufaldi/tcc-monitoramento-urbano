"""Testes do ciclo de monitoramento.

As câmeras, o YOLO e a TomTom são simulados, sem acessar a internet.
"""

import threading
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.services import ciclo_monitoramento, detection_events, flood_detection, live_detection
from app.services.ciclo_monitoramento import CameraMonitorada
from ml.detector import Deteccao

CAMERA = CameraMonitorada("http://camera-teste/1.jpg", -23.55, -46.63, "câmera teste", transito=True, alagamento=False)


def _veiculos(quantidade: int) -> list[Deteccao]:
    return [
        Deteccao(8, "veiculo", 0.8, "baixa", "observacao_visual", (i * 10, 0, i * 10 + 8, 8), "car")
        for i in range(quantidade)
    ]


class _Camera:
    """Servidor de câmera falso. Cada chamada devolve uma imagem diferente,
    a não ser que o teste peça imagem repetida ou erro."""

    def __init__(self) -> None:
        self.contador = 0
        self.modo = "nova"

    def resposta(self, _url: str):
        if self.modo == "erro":
            raise httpx.ConnectError("câmera fora do ar")
        if self.modo == "nova":
            self.contador += 1
        camera = self

        class _Resposta:
            content = f"frame-{camera.contador}".encode()
            headers = httpx.Headers({})

            def raise_for_status(self) -> None:
                return None

        return _Resposta()


@pytest.fixture
def camera(db_session: Session, tmp_path, monkeypatch) -> _Camera:
    servidor = _Camera()

    class _Cliente:
        def __init__(self, *_a, **_k) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> bool:
            return False

        def get(self, url):
            return servidor.resposta(url)

    @contextmanager
    def _sessao():
        yield db_session

    monkeypatch.setattr(ciclo_monitoramento.httpx, "Client", _Cliente)
    monkeypatch.setattr(ciclo_monitoramento, "SessionLocal", _sessao)
    monkeypatch.setattr(ciclo_monitoramento, "cameras_monitoradas", lambda: [CAMERA])
    monkeypatch.setattr(ciclo_monitoramento, "_ciclos_sem_confirmacao", {})
    monkeypatch.setattr(ciclo_monitoramento, "_ultimo_hash", {})
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _d: (content, 10, 10))
    monkeypatch.setattr(settings, "gx_ciclos_sem_confirmacao_para_remover", 2)
    _ve(monkeypatch, 0, {"disponivel": False})
    return servidor


def _ve(monkeypatch, veiculos: int, tomtom: dict) -> None:
    """Define o que o YOLO e a TomTom respondem no próximo ciclo."""
    monkeypatch.setattr(live_detection, "detectar_imagem_real", lambda _p, _t: _veiculos(veiculos))
    monkeypatch.setattr(live_detection, "obter_fluxo_transito", lambda _lat, _lon: tomtom)


def _eventos(db_session: Session) -> list[Evento]:
    db_session.expire_all()
    return db_session.query(Evento).all()


def test_segundo_ciclo_atualiza_o_mesmo_evento_e_pode_promover(db_session, camera, monkeypatch):
    """Em análise no primeiro ciclo, ativo no segundo, sem criar outro evento."""
    _ve(monkeypatch, 6, {"disponivel": True, "indice_congestionamento": 8.0})
    resumo = ciclo_monitoramento.executar_ciclo()
    assert resumo["criados"] == 1
    [evento] = _eventos(db_session)
    assert evento.status == "em_analise"
    primeiro_id = evento.id

    _ve(monkeypatch, 18, {"disponivel": False})
    resumo = ciclo_monitoramento.executar_ciclo()
    assert resumo["atualizados"] == 1 and resumo["criados"] == 0

    [evento] = _eventos(db_session)
    assert evento.id == primeiro_id
    assert evento.status == "ativo"
    assert db_session.query(EvidenciaVisual).count() == 1
    contexto = {d.chave: float(d.valor_numerico) for d in db_session.query(DadoContextual)}
    assert contexto == {"indice_congestionamento": 9.0}


def test_ativo_volta_para_analise_quando_a_nota_cai(db_session, camera, monkeypatch):
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()
    assert _eventos(db_session)[0].status == "ativo"

    _ve(monkeypatch, 6, {"disponivel": True, "indice_congestionamento": 8.0})
    ciclo_monitoramento.executar_ciclo()
    assert _eventos(db_session)[0].status == "em_analise"


def test_evento_some_no_segundo_ciclo_sem_confirmacao(db_session, camera, monkeypatch):
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()

    _ve(monkeypatch, 2, {"disponivel": False})
    resumo = ciclo_monitoramento.executar_ciclo()
    assert resumo["sem_confirmacao"] == 1
    assert len(_eventos(db_session)) == 1

    resumo = ciclo_monitoramento.executar_ciclo()
    assert resumo["removidos"] == 1
    assert _eventos(db_session) == []


def test_confirmacao_zera_a_contagem_de_ciclos_sem_ver(db_session, camera, monkeypatch):
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()
    _ve(monkeypatch, 2, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()
    _ve(monkeypatch, 2, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()

    assert len(_eventos(db_session)) == 1


def test_camera_sem_imagem_nova_nao_conta_como_falta(db_session, camera, monkeypatch):
    """Câmera fora do ar ou mandando a mesma foto: não dá para saber, então o evento fica."""
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()
    _ve(monkeypatch, 2, {"disponivel": False})

    camera.modo = "erro"
    assert ciclo_monitoramento.executar_ciclo()["sem_imagem"] == 1
    camera.modo = "repetida"
    assert ciclo_monitoramento.executar_ciclo()["sem_imagem"] == 1

    assert len(_eventos(db_session)) == 1


def test_falha_do_modelo_nao_apaga_o_evento(db_session, camera, monkeypatch):
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo()

    def _falha(_p, _t):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(live_detection, "detectar_imagem_real", _falha)
    for _ in range(3):
        assert ciclo_monitoramento.executar_ciclo()["falhas"] == 1
    assert len(_eventos(db_session)) == 1


def test_transito_e_alagamento_sao_eventos_separados(db_session, camera, monkeypatch):
    monkeypatch.setattr(ciclo_monitoramento, "cameras_monitoradas", lambda: [
        CameraMonitorada(CAMERA.snapshot_url, CAMERA.latitude, CAMERA.longitude, CAMERA.nome, transito=True, alagamento=True),
    ])
    monkeypatch.setattr(flood_detection, "detectar_incidentes_imagem", lambda _p, _t: [
        Deteccao(1, "alagamento", 0.8, "critica", "alagamento", (0, 0, 50, 50), "flood"),
    ])
    monkeypatch.setattr(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False})
    monkeypatch.setattr(flood_detection, "indice_historico", lambda _lat, _lon: (0.0, "sem histórico"))
    _ve(monkeypatch, 18, {"disponivel": False})

    ciclo_monitoramento.executar_ciclo()
    ciclo_monitoramento.executar_ciclo()

    assert sorted(e.tipo for e in _eventos(db_session)) == ["alagamento", "transito"]


def test_so_roda_um_ciclo_por_vez(camera):
    with ciclo_monitoramento._ciclo_lock:
        resumo = ciclo_monitoramento.executar_ciclo()
    assert resumo == {"executado": False, "motivo": "outro ciclo ainda está rodando"}


def test_ritmos_separam_cameras_com_e_sem_evento(db_session, camera, monkeypatch):
    """A verificação de 60 s só olha câmera sem evento, e o ciclo geral só olha câmera com evento."""
    _ve(monkeypatch, 18, {"disponivel": False})

    resumo = ciclo_monitoramento.executar_ciclo("com_evento")
    assert resumo["cameras"] == 0 and camera.contador == 0

    resumo = ciclo_monitoramento.executar_ciclo("sem_evento")
    assert resumo["criados"] == 1
    [evento] = _eventos(db_session)

    resumo = ciclo_monitoramento.executar_ciclo("sem_evento")
    assert resumo["cameras"] == 0 and camera.contador == 1

    resumo = ciclo_monitoramento.executar_ciclo("com_evento")
    assert resumo["atualizados"] == 1
    assert [e.id for e in _eventos(db_session)] == [evento.id]


def test_evento_apagado_volta_para_a_verificacao_de_60_s(db_session, camera, monkeypatch):
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo("completo")

    _ve(monkeypatch, 2, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo("com_evento")
    assert ciclo_monitoramento.executar_ciclo("com_evento")["removidos"] == 1

    assert ciclo_monitoramento.executar_ciclo("com_evento")["cameras"] == 0
    assert ciclo_monitoramento.executar_ciclo("sem_evento")["cameras"] == 1


def test_cada_tipo_segue_o_seu_ritmo(db_session, camera, monkeypatch):
    """Com evento de trânsito e sem alagamento, o alagamento continua na verificação de 60 s."""
    monkeypatch.setattr(ciclo_monitoramento, "cameras_monitoradas", lambda: [
        CameraMonitorada(CAMERA.snapshot_url, CAMERA.latitude, CAMERA.longitude, CAMERA.nome, transito=True, alagamento=True),
    ])
    vistos: list[str] = []
    monkeypatch.setattr(flood_detection, "analisar_frame", lambda *_a: vistos.append("alagamento"))
    _ve(monkeypatch, 18, {"disponivel": False})
    ciclo_monitoramento.executar_ciclo("completo")
    vistos.clear()

    ciclo_monitoramento.executar_ciclo("sem_evento")
    assert vistos == ["alagamento"]
    vistos.clear()
    assert ciclo_monitoramento.executar_ciclo("com_evento")["atualizados"] == 1
    assert vistos == []


def test_relogio_faz_passada_completa_e_depois_os_dois_ritmos(monkeypatch):
    passadas: list[str] = []
    monkeypatch.setattr(ciclo_monitoramento, "executar_ciclo", lambda modo: passadas.append(modo) or {})
    monkeypatch.setattr(settings, "gx_ciclo_minutos", 0.4 / 60)
    monkeypatch.setattr(settings, "gx_ciclo_sem_evento_segundos", 0.1)
    try:
        ciclo_monitoramento.iniciar()
        threading.Event().wait(1.0)
    finally:
        ciclo_monitoramento.parar()

    assert passadas[0] == "completo"
    assert passadas.count("completo") == 1
    assert passadas.count("sem_evento") > passadas.count("com_evento") >= 1


def test_status_do_monitoramento(client: TestClient):
    dados = client.get("/monitoramento/status").json()
    assert dados["ciclo_minutos"] == settings.gx_ciclo_minutos
    assert dados["sem_evento_segundos"] == settings.gx_ciclo_sem_evento_segundos
    assert dados["ciclos_sem_confirmacao_para_remover"] == settings.gx_ciclos_sem_confirmacao_para_remover
    assert set(dados["ultimas_passadas"]) == {"completo", "com_evento", "sem_evento"}


def test_rota_de_disparo_externo_nao_existe(client: TestClient):
    assert client.post("/monitoramento/ciclo").status_code in (404, 405)
