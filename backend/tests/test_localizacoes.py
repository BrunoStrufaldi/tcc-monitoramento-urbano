"""Testes de integração para localizações."""

from fastapi.testclient import TestClient


def test_listar_localizacoes(client: TestClient):
    response = client.get("/localizacoes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_criar_localizacao(client: TestClient):
    payload = {
        "latitude": -23.5505,
        "longitude": -46.6333,
        "endereco": "Av. Paulista, 1000",
        "bairro": "Bela Vista",
    }
    response = client.post("/localizacoes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["latitude"] == -23.5505
    assert data["endereco"] == "Av. Paulista, 1000"
    assert data["cidade"] == "São Paulo"


def test_criar_localizacao_sem_coordenadas_retorna_422(client: TestClient):
    response = client.post("/localizacoes", json={"endereco": "Sem coords"})
    assert response.status_code == 422


def test_obter_localizacao_por_id(client: TestClient):
    criar = client.post(
        "/localizacoes",
        json={"latitude": -23.56, "longitude": -46.65},
    )
    localizacao_id = criar.json()["id"]

    response = client.get(f"/localizacoes/{localizacao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == localizacao_id


def test_obter_localizacao_inexistente(client: TestClient):
    response = client.get("/localizacoes/9999")
    assert response.status_code == 404


def test_patch_atualizar_localizacao(client: TestClient):
    criar = client.post(
        "/localizacoes",
        json={"latitude": -23.55, "longitude": -46.63, "endereco": "Original"},
    )
    localizacao_id = criar.json()["id"]

    response = client.patch(
        f"/localizacoes/{localizacao_id}",
        json={"endereco": "Atualizado", "bairro": "Novo Bairro"},
    )
    assert response.status_code == 200
    assert response.json()["endereco"] == "Atualizado"
    assert response.json()["bairro"] == "Novo Bairro"


def test_patch_localizacao_inexistente(client: TestClient):
    response = client.patch("/localizacoes/9999", json={"endereco": "X"})
    assert response.status_code == 404


def test_delete_localizacao(client: TestClient):
    criar = client.post(
        "/localizacoes",
        json={"latitude": -23.55, "longitude": -46.63},
    )
    localizacao_id = criar.json()["id"]

    response = client.delete(f"/localizacoes/{localizacao_id}")
    assert response.status_code == 200
    assert response.json()["id"] == localizacao_id

    get_after = client.get(f"/localizacoes/{localizacao_id}")
    assert get_after.status_code == 404


def test_delete_localizacao_inexistente(client: TestClient):
    response = client.delete("/localizacoes/9999")
    assert response.status_code == 404


def test_delete_localizacao_com_evento_retorna_409(client: TestClient, db_session):
    from app.models.evento import Evento

    criar_loc = client.post(
        "/localizacoes",
        json={"latitude": -23.55, "longitude": -46.63},
    )
    localizacao_id = criar_loc.json()["id"]

    db_session.add(Evento(titulo="Evento na localizacao", tipo="transito", localizacao_id=localizacao_id))
    db_session.commit()

    response = client.delete(f"/localizacoes/{localizacao_id}")
    assert response.status_code == 409


def test_filtrar_por_regiao(client: TestClient):
    criar_regiao = client.post("/regioes", json={"nome": "ZL", "codigo": "ZL"})
    regiao_id = criar_regiao.json()["id"]

    client.post(
        "/localizacoes",
        json={"latitude": -23.55, "longitude": -46.63, "regiao_id": regiao_id},
    )

    response = client.get(f"/localizacoes?regiao_id={regiao_id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
