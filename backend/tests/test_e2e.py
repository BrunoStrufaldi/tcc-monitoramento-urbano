"""Testes end-to-end — fluxo completo do sistema de notificações urbanas.

O sistema não tem operador: o evento nasce da detecção automática e é o próprio
backend que o promove, recalcula e purga. O painel só consulta. Estes fluxos
percorrem esse caminho — não as rotas de escrita, que não existem mais.
"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def _criar_regiao(client: TestClient) -> int:
    r = client.post("/regioes", json={"nome": "Centro", "descricao": "Região central"})
    return r.json()["id"]


def _criar_fonte(client: TestClient) -> int:
    r = client.post(
        "/fontes",
        json={"nome": "Câmera Via App", "tipo": "camera", "url": "http://exemplo.com/cam"},
    )
    return r.json()["id"]


def test_fluxo_evento_detectado_ate_consulta(client: TestClient, db_session, criar_evento, criar_evidencia):
    """Evento detectado → evidência → dado contextual → consultas do painel."""
    regiao_id = _criar_regiao(client)
    fonte_id = _criar_fonte(client)

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

    # 4. Dado contextual (clima) — essa rota de escrita continua, é ingestão de fonte
    ctx = client.post(
        "/dados-contextuais",
        json={
            "evento_id": evento_id,
            "categoria": "clima",
            "chave": "precipitacao",
            "valor_texto": "Chuva de 45mm/h nas últimas 2 horas",
        },
    )
    assert ctx.status_code == 201
    assert len(client.get(f"/dados-contextuais?evento_id={evento_id}").json()) == 1

    # 5. Logs do evento respondem
    assert client.get(f"/logs?evento_id={evento_id}").status_code == 200


def test_fluxo_deteccao_yolo_simulada(client: TestClient):
    """A simulação de detecção devolve os campos que o pipeline usaria."""
    deteccao = client.post("/deteccao/simular", json={"num_deteccoes": 2})
    assert deteccao.status_code == 200
    resultados = deteccao.json()
    assert len(resultados) == 2

    det = resultados[0]
    assert det["severidade"] in ("baixa", "media", "alta", "critica")
    assert 0 <= det["confianca"] <= 1
    assert det["tipo"]


def test_fluxo_fusao_dados(client: TestClient, criar_evento):
    """Consulta e recálculo da confiabilidade de um evento detectado."""
    evento = criar_evento(titulo="Incêndio em prédio", tipo="incendio", severidade="critica")

    fusao = client.get(f"/fusion/eventos/{evento.id}/confiabilidade")
    assert fusao.status_code == 200
    dados = fusao.json()
    assert "confiabilidade" in dados
    assert dados["nivel"] in ("alta", "media", "baixa")

    recalculo = client.post(f"/fusion/eventos/{evento.id}/recalcular")
    assert recalculo.status_code == 200
    assert recalculo.json()["nivel"] in ("alta", "media", "baixa")


def test_fluxo_retencao_remove_evento_expirado(client: TestClient, db_session, criar_evento):
    """A retenção automática é quem tira o evento do quadro — não uma rota."""
    from app.services.event_retention import purgar_eventos_expirados

    evento = criar_evento(titulo="Evento antigo", tipo="transito")
    evento_id = evento.id
    evento.detectado_em = datetime.now() - timedelta(days=30)
    db_session.commit()

    assert client.get(f"/eventos/{evento_id}").status_code == 200

    purgar_eventos_expirados(db_session)

    assert client.get(f"/eventos/{evento_id}").status_code == 404


def test_health_e_raiz(client: TestClient):
    """Verifica endpoints de saúde do sistema."""
    raiz = client.get("/")
    assert raiz.status_code == 200
    assert raiz.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
