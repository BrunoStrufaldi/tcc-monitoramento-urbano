"""Testes de integração para dados contextuais (somente leitura).

Quem grava dado contextual é a coleta automática (clima, INMET, trânsito) —
nunca uma rota pública.
"""

from fastapi.testclient import TestClient

from app.models.dado_contextual import DadoContextual


def _criar_dado(db_session, **campos) -> DadoContextual:
    campos.setdefault("categoria", "contexto")
    campos.setdefault("chave", "temp")
    dado = DadoContextual(**campos)
    db_session.add(dado)
    db_session.commit()
    db_session.refresh(dado)
    return dado


def test_listar_dados_contextuais_vazio(client: TestClient):
    response = client.get("/dados-contextuais")
    assert response.status_code == 200
    assert response.json() == []


def test_obter_dado_contextual_por_id(client: TestClient, db_session, criar_evento):
    dado = _criar_dado(
        db_session,
        evento_id=criar_evento().id,
        chave="precipitacao_mm_h",
        valor_numerico=45.2,
        unidade="mm/h",
    )
    response = client.get(f"/dados-contextuais/{dado.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["chave"] == "precipitacao_mm_h"
    assert data["valor_numerico"] == 45.2


def test_obter_dado_contextual_inexistente(client: TestClient):
    response = client.get("/dados-contextuais/9999")
    assert response.status_code == 404


def test_filtrar_por_evento(client: TestClient, db_session, criar_evento):
    evento_id = criar_evento().id
    _criar_dado(db_session, evento_id=evento_id, chave="temp", valor_numerico=25)
    _criar_dado(db_session, evento_id=evento_id, chave="umidade", valor_numerico=80)
    _criar_dado(db_session, chave="sem_evento")

    response = client.get(f"/dados-contextuais?evento_id={evento_id}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filtrar_por_categoria(client: TestClient, db_session):
    _criar_dado(db_session, categoria="contexto")
    _criar_dado(db_session, categoria="outra")

    response = client.get("/dados-contextuais?categoria=contexto")
    assert response.status_code == 200
    assert [d["categoria"] for d in response.json()] == ["contexto"]


def test_escrita_em_dados_contextuais_nao_existe(client: TestClient, db_session):
    """Um POST público deixaria qualquer um injetar "chuva" e inflar a fusão."""
    dado = _criar_dado(db_session)

    payload = {"categoria": "clima", "chave": "precipitacao", "valor_numerico": 99}
    assert client.post("/dados-contextuais", json=payload).status_code == 405
    assert client.delete(f"/dados-contextuais/{dado.id}").status_code == 405
