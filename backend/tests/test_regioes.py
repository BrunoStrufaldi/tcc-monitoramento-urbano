"""Testes de integração para regiões."""

from fastapi.testclient import TestClient


def test_listar_regioes(client: TestClient):
    response = client.get("/regioes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_criar_regiao(client: TestClient):
    payload = {"nome": "Zona Leste", "codigo": "ZL", "descricao": "Bairros da zona leste"}
    response = client.post("/regioes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Zona Leste"
    assert data["codigo"] == "ZL"
    assert data["ativo"] is True


def test_obter_regiao_por_id(client: TestClient):
    criar = client.post("/regioes", json={"nome": "Teste", "codigo": "TST"})
    regiao_id = criar.json()["id"]
    response = client.get(f"/regioes/{regiao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == regiao_id


def test_obter_regiao_inexistente(client: TestClient):
    response = client.get("/regioes/9999")
    assert response.status_code == 404


def test_patch_atualizar_regiao(client: TestClient):
    criar = client.post("/regioes", json={"nome": "Original", "codigo": "ORI"})
    regiao_id = criar.json()["id"]
    response = client.patch(f"/regioes/{regiao_id}", json={"nome": "Atualizada"})
    assert response.status_code == 200
    assert response.json()["nome"] == "Atualizada"


def test_patch_desativar_regiao(client: TestClient):
    criar = client.post("/regioes", json={"nome": "Para desativar", "codigo": "PD"})
    regiao_id = criar.json()["id"]
    response = client.patch(f"/regioes/{regiao_id}", json={"ativo": False})
    assert response.status_code == 200
    assert response.json()["ativo"] is False


def test_filtrar_por_ativo(client: TestClient):
    response = client.get("/regioes?ativo=true")
    assert response.status_code == 200


def test_delete_regiao(client: TestClient):
    criar = client.post("/regioes", json={"nome": "Para remover", "codigo": "PR"})
    regiao_id = criar.json()["id"]

    response = client.delete(f"/regioes/{regiao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == regiao_id

    get_after = client.get(f"/regioes/{regiao_id}")
    assert get_after.status_code == 404


def test_delete_regiao_inexistente(client: TestClient):
    response = client.delete("/regioes/9999")
    assert response.status_code == 404
