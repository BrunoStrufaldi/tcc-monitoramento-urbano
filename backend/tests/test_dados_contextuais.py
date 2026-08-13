"""Testes de integração para dados contextuais."""

from fastapi.testclient import TestClient


def _criar_evento(client: TestClient) -> int:
    r = client.post(
        "/eventos",
        json={"titulo": "Evento teste", "tipo": "alagamento", "latitude": -23.55, "longitude": -46.63},
    )
    return r.json()["id"]


def test_listar_dados_contextuais_vazio(client: TestClient):
    response = client.get("/dados-contextuais")
    assert response.status_code == 200
    assert response.json() == []


def test_criar_dado_contextual(client: TestClient):
    evento_id = _criar_evento(client)
    payload = {
        "evento_id": evento_id,
        "categoria": "clima",
        "chave": "precipitacao_mm_h",
        "valor_numerico": 45.2,
        "unidade": "mm/h",
    }
    response = client.post("/dados-contextuais", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["categoria"] == "clima"
    assert data["chave"] == "precipitacao_mm_h"
    assert data["valor_numerico"] == 45.2


def test_criar_dado_contextual_texto(client: TestClient):
    payload = {
        "categoria": "social",
        "chave": "sentimento",
        "valor_texto": "negativo",
    }
    response = client.post("/dados-contextuais", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["valor_texto"] == "negativo"
    assert data["evento_id"] is None


def test_criar_dado_contextual_campos_obrigatorios(client: TestClient):
    response = client.post("/dados-contextuais", json={"categoria": "clima"})
    assert response.status_code == 422


def test_obter_dado_contextual_por_id(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/dados-contextuais",
        json={"evento_id": evento_id, "categoria": "transito", "chave": "velocidade", "valor_numerico": 20},
    )
    dado_id = criar.json()["id"]

    response = client.get(f"/dados-contextuais/{dado_id}")
    assert response.status_code == 200
    assert response.json()["id"] == dado_id


def test_obter_dado_contextual_inexistente(client: TestClient):
    response = client.get("/dados-contextuais/9999")
    assert response.status_code == 404


def test_delete_dado_contextual(client: TestClient):
    criar = client.post(
        "/dados-contextuais",
        json={"categoria": "test", "chave": "delete_me", "valor_texto": "x"},
    )
    dado_id = criar.json()["id"]

    response = client.delete(f"/dados-contextuais/{dado_id}")
    assert response.status_code == 200
    assert response.json()["id"] == dado_id

    get_after = client.get(f"/dados-contextuais/{dado_id}")
    assert get_after.status_code == 404


def test_delete_dado_contextual_inexistente(client: TestClient):
    response = client.delete("/dados-contextuais/9999")
    assert response.status_code == 404


def test_filtrar_por_evento(client: TestClient):
    evento_id = _criar_evento(client)
    client.post(
        "/dados-contextuais",
        json={"evento_id": evento_id, "categoria": "clima", "chave": "temp", "valor_numerico": 25},
    )
    client.post(
        "/dados-contextuais",
        json={"evento_id": evento_id, "categoria": "clima", "chave": "umidade", "valor_numerico": 80},
    )

    response = client.get(f"/dados-contextuais?evento_id={evento_id}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filtrar_por_categoria(client: TestClient):
    client.post(
        "/dados-contextuais",
        json={"categoria": "clima", "chave": "temp", "valor_numerico": 25},
    )
    client.post(
        "/dados-contextuais",
        json={"categoria": "social", "chave": "posts", "valor_numerico": 150},
    )

    response = client.get("/dados-contextuais?categoria=clima")
    assert response.status_code == 200
    assert all(d["categoria"] == "clima" for d in response.json())
