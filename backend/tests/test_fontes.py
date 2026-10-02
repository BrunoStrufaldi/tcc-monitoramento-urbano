"""Testes de integração para fontes de dados (somente leitura)."""

from fastapi.testclient import TestClient

from app.models.fonte_dados import FonteDados


def _criar_fonte(db_session, **campos) -> FonteDados:
    campos.setdefault("nome", "Câmera YOLO")
    campos.setdefault("tipo", "yolo")
    fonte = FonteDados(**campos)
    db_session.add(fonte)
    db_session.commit()
    db_session.refresh(fonte)
    return fonte


def test_listar_fontes(client: TestClient, db_session):
    _criar_fonte(db_session)
    response = client.get("/fontes")
    assert response.status_code == 200
    assert [f["tipo"] for f in response.json()] == ["yolo"]


def test_obter_fonte_por_id(client: TestClient, db_session):
    fonte = _criar_fonte(db_session)
    response = client.get(f"/fontes/{fonte.id}")
    assert response.status_code == 200
    assert response.json()["id"] == fonte.id


def test_obter_fonte_inexistente(client: TestClient):
    response = client.get("/fontes/9999")
    assert response.status_code == 404


def test_filtrar_por_tipo(client: TestClient, db_session):
    _criar_fonte(db_session, nome="Câmera", tipo="yolo")
    _criar_fonte(db_session, nome="INMET", tipo="clima")
    response = client.get("/fontes?tipo=clima")
    assert response.status_code == 200
    assert [f["nome"] for f in response.json()] == ["INMET"]


def test_escrita_em_fontes_nao_existe(client: TestClient, db_session):
    fonte = _criar_fonte(db_session)

    assert client.post("/fontes", json={"nome": "X", "tipo": "api"}).status_code == 405
    assert client.patch(f"/fontes/{fonte.id}", json={"ativo": False}).status_code == 405
    assert client.delete(f"/fontes/{fonte.id}").status_code == 405
