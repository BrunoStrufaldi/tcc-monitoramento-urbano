"""Testes de integração para evidências visuais.

``/evidencias`` é somente consulta: as evidências são gravadas pela
detecção (``services/detection_events.py``), nunca por requisição.
"""

from fastapi.testclient import TestClient


def test_pasta_de_arquivo_bate_com_a_pasta_onde_detection_events_grava():
    """Regressão: o router já serviu arquivo de uma pasta diferente de onde
    detection_events.py grava (parents[2] vs parents[1]) — toda evidência
    criada por detecção real (câmera contínua, confirmação manual) resultava
    em 404 ao tentar exibir a imagem, mesmo o arquivo existindo de verdade."""
    from app.routers import evidencias
    from app.services import detection_events

    assert evidencias._EVIDENCIAS_DIR == detection_events._EVIDENCIAS_DIR


def test_obter_arquivo_de_evidencia(client: TestClient, tmp_path, monkeypatch):
    from app.routers import evidencias

    monkeypatch.setattr(evidencias, "_EVIDENCIAS_DIR", tmp_path)
    (tmp_path / "foto-teste.jpg").write_bytes(b"conteudo-fake-de-imagem")

    response = client.get("/evidencias/arquivo/foto-teste.jpg")
    assert response.status_code == 200
    assert response.content == b"conteudo-fake-de-imagem"


def test_obter_arquivo_de_evidencia_inexistente(client: TestClient, tmp_path, monkeypatch):
    from app.routers import evidencias

    monkeypatch.setattr(evidencias, "_EVIDENCIAS_DIR", tmp_path)
    response = client.get("/evidencias/arquivo/nao-existe.jpg")
    assert response.status_code == 404


def test_listar_evidencias_vazio(client: TestClient):
    response = client.get("/evidencias")
    assert response.status_code == 200
    assert response.json() == []


def test_obter_evidencia_por_id(client: TestClient, criar_evento, criar_evidencia):
    evento = criar_evento()
    evidencia = criar_evidencia(evento.id, tipo="imagem", classe_detectada="carro", confianca=0.91)

    response = client.get(f"/evidencias/{evidencia.id}")
    assert response.status_code == 200
    dados = response.json()
    assert dados["id"] == evidencia.id
    assert dados["classe_detectada"] == "carro"


def test_obter_evidencia_inexistente(client: TestClient):
    response = client.get("/evidencias/9999")
    assert response.status_code == 404


def test_filtrar_por_evento(client: TestClient, criar_evento, criar_evidencia):
    evento = criar_evento()
    outro = criar_evento(titulo="Outro evento")
    criar_evidencia(evento.id)
    criar_evidencia(evento.id)
    criar_evidencia(outro.id)

    response = client.get(f"/evidencias?evento_id={evento.id}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filtrar_por_tipo(client: TestClient, criar_evento, criar_evidencia):
    evento = criar_evento()
    criar_evidencia(evento.id, tipo="imagem")
    criar_evidencia(evento.id, tipo="video")

    response = client.get("/evidencias?tipo=video")
    assert response.status_code == 200
    assert [item["tipo"] for item in response.json()] == ["video"]


def test_escrita_em_evidencias_nao_existe(client: TestClient, criar_evento, criar_evidencia):
    """O painel não registra evidência na mão — quem grava é a detecção."""
    evento = criar_evento()
    evidencia = criar_evidencia(evento.id)

    assert client.post("/evidencias", json={"evento_id": evento.id, "tipo": "imagem"}).status_code == 405
    assert client.delete(f"/evidencias/{evidencia.id}").status_code == 405
