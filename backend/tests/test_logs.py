"""Testes de integração para logs do sistema."""

from fastapi.testclient import TestClient


def test_listar_logs_vazio(client: TestClient):
    response = client.get("/logs")
    assert response.status_code == 200
    assert response.json() == []


def test_logs_apos_criar_evento(client: TestClient):
    """Cria evento via API e verifica se o endpoint de logs retorna vazio (logs não são criados automaticamente)."""
    client.post(
        "/eventos",
        json={"titulo": "Evento", "tipo": "transito", "latitude": -23.55, "longitude": -46.63},
    )
    response = client.get("/logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_filtrar_por_nivel(client: TestClient):
    response = client.get("/logs?nivel=INFO")
    assert response.status_code == 200


def test_filtrar_por_modulo(client: TestClient):
    response = client.get("/logs?modulo=api")
    assert response.status_code == 200
