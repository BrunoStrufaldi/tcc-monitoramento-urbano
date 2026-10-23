"""Testes de ponta a ponta do MotSP.

O evento nasce da detecção automática e o painel só consulta. Estes testes
seguem esse caminho.
"""

from fastapi.testclient import TestClient

from app.models.dado_contextual import DadoContextual
from app.models.fonte_dados import FonteDados
from app.models.regiao import Regiao


def _criar_regiao(db_session) -> int:
    regiao = Regiao(nome="Centro", descricao="Região central")
    db_session.add(regiao)
    db_session.commit()
    return regiao.id


def _criar_fonte(db_session) -> int:
    fonte = FonteDados(nome="Câmera Via App", tipo="camera", endpoint="http://exemplo.com/cam")
    db_session.add(fonte)
    db_session.commit()
    return fonte.id


def test_fluxo_evento_detectado_ate_consulta(client: TestClient, db_session, criar_evento, criar_evidencia):
    """Evento detectado, evidência, dado de contexto e consultas do painel."""
    regiao_id = _criar_regiao(db_session)
    fonte_id = _criar_fonte(db_session)

    evento = criar_evento(
        titulo="Alagamento na Av. Paulista",
        descricao="Alagamento severo após chuva forte",
        tipo="alagamento",
        severidade="critica",
        status="ativo",
        regiao_id=regiao_id,
        fonte_id=fonte_id,
        confianca=0.85,
    )
    evento_id = evento.id

    # 1. Aparece na listagem do painel
    listar = client.get("/eventos")
    assert any(item["id"] == evento_id for item in listar.json())

    # 2. Detalhe traz os campos e os relacionamentos
    detalhe = client.get(f"/eventos/{evento_id}").json()
    assert detalhe["titulo"] == "Alagamento na Av. Paulista"
    assert detalhe["severidade"] == "critica"
    assert float(detalhe["confianca"]) == 0.85

    # 3. Evidência gravada pela detecção
    criar_evidencia(evento_id, tipo="imagem", classe_detectada="alagamento", confianca=0.88)
    evid_list = client.get(f"/evidencias?evento_id={evento_id}")
    assert len(evid_list.json()) == 1

    # 4. Dado contextual (chuva) gravado pela coleta automática
    db_session.add(
        DadoContextual(
            evento_id=evento_id,
            categoria="contexto",
            chave="precipitacao",
            valor_texto="Chuva de 45mm/h nas últimas 2 horas",
        )
    )
    db_session.commit()
    assert len(client.get(f"/dados-contextuais?evento_id={evento_id}").json()) == 1

    # 5. Logs do evento respondem
    assert client.get(f"/logs?evento_id={evento_id}").status_code == 200


def test_fluxo_fusao_dados(client: TestClient, criar_evento):
    """Consulta e recálculo da confiabilidade de um evento detectado."""
    evento = criar_evento(titulo="Incêndio em prédio", tipo="incendio", severidade="critica")

    fusao = client.get(f"/fusion/eventos/{evento.id}/confiabilidade")
    assert fusao.status_code == 200
    dados = fusao.json()
    assert "confiabilidade" in dados
    assert dados["nivel"] in ("alta", "media", "baixa")
    assert [c["nome"] for c in dados["componentes"]] == ["ia", "contexto"]

    recalculo = client.post(f"/fusion/eventos/{evento.id}/recalcular")
    assert recalculo.status_code == 200
    assert recalculo.json()["nivel"] in ("alta", "media", "baixa")


def test_painel_e_status_da_api(client: TestClient):
    assert client.get("/api/status").json()["status"] == "online"
    assert client.get("/health").json()["status"] == "ok"

    # "/" é o painel: a API serve o frontend na mesma origem.
    raiz = client.get("/")
    assert raiz.status_code == 200
    assert "text/html" in raiz.headers["content-type"]

    # O app.js e o fusion-format.js precisam ser revalidados juntos pelo navegador.
    assert raiz.headers["cache-control"] == "no-cache"
    assert client.get("/dist/app.js").headers["cache-control"] == "no-cache"
    assert client.get("/dist/fusion-format.js").headers["cache-control"] == "no-cache"
    assert "cache-control" not in client.get("/css/style.css").headers
