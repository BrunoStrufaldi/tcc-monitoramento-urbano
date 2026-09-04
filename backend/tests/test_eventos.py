"""Testes de integração dos endpoints principais.

O painel é somente leitura: ``/eventos`` só expõe consulta. Os eventos são
montados direto no banco pelas fábricas do ``conftest`` — o mesmo caminho que
``services/detection_events.py`` usa ao gravar uma detecção real.
"""

from fastapi.testclient import TestClient


def test_raiz_retorna_status_online(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_listar_eventos_vazio(client: TestClient):
    response = client.get("/eventos")
    assert response.status_code == 200
    assert response.json() == []


def test_listar_evento_detectado(client: TestClient, criar_evento):
    criar_evento(
        titulo="Teste de alagamento",
        tipo="alagamento",
        severidade="alta",
        status="ativo",
        latitude=-23.5505,
        longitude=-46.6333,
    )

    listar = client.get("/eventos")
    assert listar.status_code == 200
    dados = listar.json()
    assert len(dados) == 1
    assert dados[0]["titulo"] == "Teste de alagamento"
    assert dados[0]["latitude"] == -23.5505
    assert dados[0]["longitude"] == -46.6333


def test_obter_evento_por_id(client: TestClient, criar_evento):
    evento = criar_evento(titulo="Evento específico", tipo="transito")

    response = client.get(f"/eventos/{evento.id}")
    assert response.status_code == 200
    assert response.json()["id"] == evento.id


def test_obter_evento_inexistente_retorna_404(client: TestClient):
    response = client.get("/eventos/9999")
    assert response.status_code == 404


def test_filtrar_eventos_por_status(client: TestClient, criar_evento):
    for status in ["ativo", "resolvido"]:
        criar_evento(titulo=f"Evento {status}", tipo="transito", status=status)

    ativos = client.get("/eventos?status=ativo")
    assert len(ativos.json()) == 1
    assert ativos.json()[0]["status"] == "ativo"

    resolvidos = client.get("/eventos?status=resolvido")
    assert len(resolvidos.json()) == 1
    assert resolvidos.json()[0]["status"] == "resolvido"


def test_filtrar_eventos_por_tipo(client: TestClient, criar_evento):
    criar_evento(titulo="Alagamento", tipo="alagamento")
    criar_evento(titulo="Trânsito", tipo="transito")

    response = client.get("/eventos?tipo=alagamento")
    assert response.status_code == 200
    assert [item["tipo"] for item in response.json()] == ["alagamento"]


def test_escrita_em_eventos_nao_existe(client: TestClient, criar_evento):
    """O painel não cria, altera nem remove evento — as rotas não existem."""
    evento = criar_evento()

    assert client.post("/eventos", json={"titulo": "x", "tipo": "transito"}).status_code == 405
    assert client.patch(f"/eventos/{evento.id}", json={"status": "resolvido"}).status_code == 405
    assert client.delete(f"/eventos/{evento.id}").status_code == 405
