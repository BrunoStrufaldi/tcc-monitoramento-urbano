"""Testes de integração para localizações (somente leitura)."""

from fastapi.testclient import TestClient

from app.models.localizacao import Localizacao
from app.models.regiao import Regiao


def _criar_localizacao(db_session, **campos) -> Localizacao:
    campos.setdefault("latitude", -23.5505)
    campos.setdefault("longitude", -46.6333)
    localizacao = Localizacao(**campos)
    db_session.add(localizacao)
    db_session.commit()
    db_session.refresh(localizacao)
    return localizacao


def test_listar_localizacoes(client: TestClient, db_session):
    _criar_localizacao(db_session, endereco="Av. Paulista, 1000")
    response = client.get("/localizacoes")
    assert response.status_code == 200
    data = response.json()
    assert [loc["endereco"] for loc in data] == ["Av. Paulista, 1000"]
    assert data[0]["cidade"] == "São Paulo"


def test_obter_localizacao_por_id(client: TestClient, db_session):
    localizacao = _criar_localizacao(db_session)
    response = client.get(f"/localizacoes/{localizacao.id}")
    assert response.status_code == 200
    assert response.json()["id"] == localizacao.id


def test_obter_localizacao_inexistente(client: TestClient):
    response = client.get("/localizacoes/9999")
    assert response.status_code == 404


def test_filtrar_por_regiao(client: TestClient, db_session):
    regiao = Regiao(nome="ZL", codigo="ZL")
    db_session.add(regiao)
    db_session.commit()
    _criar_localizacao(db_session, regiao_id=regiao.id)
    _criar_localizacao(db_session)

    response = client.get(f"/localizacoes?regiao_id={regiao.id}")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_escrita_em_localizacoes_nao_existe(client: TestClient, db_session):
    localizacao = _criar_localizacao(db_session)

    assert client.post("/localizacoes", json={"latitude": 0, "longitude": 0}).status_code == 405
    assert client.patch(f"/localizacoes/{localizacao.id}", json={"endereco": "X"}).status_code == 405
    assert client.delete(f"/localizacoes/{localizacao.id}").status_code == 405
