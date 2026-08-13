"""Testes de integração para fontes de dados."""

from fastapi.testclient import TestClient


def test_listar_fontes(client: TestClient):
    response = client.get("/fontes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_criar_fonte(client: TestClient):
    payload = {"nome": "Câmera YOLO", "tipo": "yolo", "descricao": "Detecção por câmera"}
    response = client.post("/fontes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Câmera YOLO"
    assert data["tipo"] == "yolo"
    assert data["ativo"] is True


def test_obter_fonte_por_id(client: TestClient):
    criar = client.post("/fontes", json={"nome": "Sensor Teste", "tipo": "sensor"})
    fonte_id = criar.json()["id"]
    response = client.get(f"/fontes/{fonte_id}")
    assert response.status_code == 200
    assert response.json()["id"] == fonte_id


def test_obter_fonte_inexistente(client: TestClient):
    response = client.get("/fontes/9999")
    assert response.status_code == 404


def test_patch_atualizar_fonte(client: TestClient):
    criar = client.post("/fontes", json={"nome": "Original", "tipo": "api"})
    fonte_id = criar.json()["id"]
    response = client.patch(f"/fontes/{fonte_id}", json={"nome": "Atualizada"})
    assert response.status_code == 200
    assert response.json()["nome"] == "Atualizada"


def test_patch_desativar_fonte(client: TestClient):
    criar = client.post("/fontes", json={"nome": "Para desativar", "tipo": "manual"})
    fonte_id = criar.json()["id"]
    response = client.patch(f"/fontes/{fonte_id}", json={"ativo": False})
    assert response.status_code == 200
    assert response.json()["ativo"] is False


def test_filtrar_por_tipo(client: TestClient):
    response = client.get("/fontes?tipo=sensor")
    assert response.status_code == 200


def test_delete_fonte(client: TestClient):
    criar = client.post("/fontes", json={"nome": "Para remover", "tipo": "manual"})
    fonte_id = criar.json()["id"]

    response = client.delete(f"/fontes/{fonte_id}")
    assert response.status_code == 200
    assert response.json()["id"] == fonte_id

    get_after = client.get(f"/fontes/{fonte_id}")
    assert get_after.status_code == 404


def test_delete_fonte_inexistente(client: TestClient):
    response = client.delete("/fontes/9999")
    assert response.status_code == 404
