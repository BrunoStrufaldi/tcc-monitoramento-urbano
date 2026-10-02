"""Testes de integração para regiões (somente leitura)."""

from fastapi.testclient import TestClient

from app.models.regiao import Regiao


def _criar_regiao(db_session, **campos) -> Regiao:
    campos.setdefault("nome", "Zona Leste")
    regiao = Regiao(**campos)
    db_session.add(regiao)
    db_session.commit()
    db_session.refresh(regiao)
    return regiao


def test_listar_regioes(client: TestClient, db_session):
    _criar_regiao(db_session, nome="Zona Leste", codigo="ZL")
    response = client.get("/regioes")
    assert response.status_code == 200
    assert [r["codigo"] for r in response.json()] == ["ZL"]


def test_obter_regiao_por_id(client: TestClient, db_session):
    regiao = _criar_regiao(db_session, codigo="TST")
    response = client.get(f"/regioes/{regiao.id}")
    assert response.status_code == 200
    assert response.json()["id"] == regiao.id


def test_obter_regiao_inexistente(client: TestClient):
    response = client.get("/regioes/9999")
    assert response.status_code == 404


def test_filtrar_por_ativo(client: TestClient, db_session):
    _criar_regiao(db_session, nome="Ativa")
    _criar_regiao(db_session, nome="Inativa", ativo=False)
    response = client.get("/regioes?ativo=true")
    assert response.status_code == 200
    assert [r["nome"] for r in response.json()] == ["Ativa"]


def test_escrita_em_regioes_nao_existe(client: TestClient, db_session):
    """Sem login no deploy, rota de escrita pública deixaria qualquer um alterar dados."""
    regiao = _criar_regiao(db_session)

    assert client.post("/regioes", json={"nome": "X"}).status_code == 405
    assert client.patch(f"/regioes/{regiao.id}", json={"nome": "Y"}).status_code == 405
    assert client.delete(f"/regioes/{regiao.id}").status_code == 405
