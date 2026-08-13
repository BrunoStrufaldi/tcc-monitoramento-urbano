"""Testes de integração para notificações."""

from fastapi.testclient import TestClient


def _criar_evento(client: TestClient) -> int:
    """Helper: cria um evento e retorna o ID."""
    r = client.post(
        "/eventos",
        json={"titulo": "Evento teste", "tipo": "alagamento", "latitude": -23.55, "longitude": -46.63},
    )
    return r.json()["id"]


def test_listar_notificacoes_vazio(client: TestClient):
    response = client.get("/notificacoes")
    assert response.status_code == 200
    assert response.json() == []


def test_criar_notificacao(client: TestClient):
    evento_id = _criar_evento(client)
    payload = {
        "evento_id": evento_id,
        "canal": "painel",
        "titulo": "Alerta teste",
        "mensagem": "Mensagem de teste",
    }
    response = client.post("/notificacoes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["titulo"] == "Alerta teste"
    assert data["status"] == "pendente"


def test_criar_notificacao_evento_inexistente(client: TestClient):
    payload = {
        "evento_id": 9999,
        "canal": "push",
        "titulo": "Sem evento",
        "mensagem": "Erro esperado",
    }
    response = client.post("/notificacoes", json=payload)
    assert response.status_code == 404


def test_obter_notificacao_por_id(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Buscar por ID", "mensagem": "teste"},
    )
    notificacao_id = criar.json()["id"]

    response = client.get(f"/notificacoes/{notificacao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == notificacao_id
    assert response.json()["titulo"] == "Buscar por ID"


def test_obter_notificacao_inexistente(client: TestClient):
    response = client.get("/notificacoes/9999")
    assert response.status_code == 404


def test_marcar_como_lida(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Para ler", "mensagem": "Teste"},
    )
    notificacao_id = criar.json()["id"]

    response = client.patch(f"/notificacoes/{notificacao_id}/lida")
    assert response.status_code == 200
    assert response.json()["status"] == "lida"
    assert response.json()["lida_em"] is not None


def test_marcar_lida_inexistente(client: TestClient):
    response = client.patch("/notificacoes/9999/lida")
    assert response.status_code == 404


def test_arquivar_notificacao(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Para arquivar", "mensagem": "Teste"},
    )
    notificacao_id = criar.json()["id"]

    response = client.patch(f"/notificacoes/{notificacao_id}/arquivar")
    assert response.status_code == 200
    assert response.json()["status"] == "arquivada"


def test_arquivar_inexistente(client: TestClient):
    response = client.patch("/notificacoes/9999/arquivar")
    assert response.status_code == 404


def test_patch_atualizar_notificacao(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Original", "mensagem": "Teste"},
    )
    notificacao_id = criar.json()["id"]

    response = client.patch(f"/notificacoes/{notificacao_id}", json={"titulo": "Atualizado"})
    assert response.status_code == 200
    assert response.json()["titulo"] == "Atualizado"
    assert response.json()["status"] == "pendente"


def test_patch_notificacao_inexistente(client: TestClient):
    response = client.patch("/notificacoes/9999", json={"titulo": "X"})
    assert response.status_code == 404


def test_delete_notificacao(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Para remover", "mensagem": "Teste"},
    )
    notificacao_id = criar.json()["id"]

    response = client.delete(f"/notificacoes/{notificacao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == notificacao_id

    get_after = client.get(f"/notificacoes/{notificacao_id}")
    assert get_after.status_code == 404


def test_delete_notificacao_inexistente(client: TestClient):
    response = client.delete("/notificacoes/9999")
    assert response.status_code == 404


def test_filtrar_por_evento(client: TestClient):
    evento_id = _criar_evento(client)
    client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "N1", "mensagem": "m"},
    )
    client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "N2", "mensagem": "m"},
    )

    response = client.get(f"/notificacoes?evento_id={evento_id}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filtrar_por_status(client: TestClient):
    evento_id = _criar_evento(client)
    client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Pendente", "mensagem": "m"},
    )
    criar_lida = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Lida", "mensagem": "m"},
    )
    client.patch(f"/notificacoes/{criar_lida.json()['id']}/lida")

    pendentes = client.get("/notificacoes?status=pendente")
    assert len(pendentes.json()) == 1

    lidas = client.get("/notificacoes?status=lida")
    assert len(lidas.json()) == 1


def test_criar_notificacao_canal_invalido_retorna_422(client: TestClient):
    evento_id = _criar_evento(client)
    response = client.post(
        "/notificacoes",
        json={"evento_id": evento_id, "titulo": "Teste", "mensagem": "m", "canal": "fax"},
    )
    assert response.status_code == 422
