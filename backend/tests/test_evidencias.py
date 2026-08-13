"""Testes de integração para evidências visuais."""

from fastapi.testclient import TestClient


def _criar_evento(client: TestClient) -> int:
    r = client.post(
        "/eventos",
        json={"titulo": "Evento teste", "tipo": "incendio", "latitude": -23.55, "longitude": -46.63},
    )
    return r.json()["id"]


def test_listar_evidencias_vazio(client: TestClient):
    response = client.get("/evidencias")
    assert response.status_code == 200
    assert response.json() == []


def test_criar_evidencia(client: TestClient):
    evento_id = _criar_evento(client)
    payload = {
        "evento_id": evento_id,
        "tipo": "imagem",
        "url_externa": "https://exemplo.com/foto.jpg",
        "modelo_ia": "yolov8n",
        "classe_detectada": "fire",
        "confianca": 0.85,
    }
    response = client.post("/evidencias", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["tipo"] == "imagem"
    assert data["classe_detectada"] == "fire"
    assert data["evento_id"] == evento_id


def test_criar_evidencia_evento_inexistente(client: TestClient):
    payload = {
        "evento_id": 9999,
        "tipo": "video",
        "url_externa": "https://exemplo.com/video.mp4",
    }
    response = client.post("/evidencias", json=payload)
    assert response.status_code == 404


def test_obter_evidencia_por_id(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/evidencias",
        json={"evento_id": evento_id, "tipo": "frame", "url_externa": "https://exemplo.com/frame.jpg"},
    )
    evidencia_id = criar.json()["id"]

    response = client.get(f"/evidencias/{evidencia_id}")
    assert response.status_code == 200
    assert response.json()["id"] == evidencia_id


def test_obter_evidencia_inexistente(client: TestClient):
    response = client.get("/evidencias/9999")
    assert response.status_code == 404


def test_delete_evidencia(client: TestClient):
    evento_id = _criar_evento(client)
    criar = client.post(
        "/evidencias",
        json={"evento_id": evento_id, "tipo": "thumbnail", "url_externa": "https://exemplo.com/thumb.jpg"},
    )
    evidencia_id = criar.json()["id"]

    response = client.delete(f"/evidencias/{evidencia_id}")
    assert response.status_code == 200
    assert response.json()["id"] == evidencia_id

    get_after = client.get(f"/evidencias/{evidencia_id}")
    assert get_after.status_code == 404


def test_delete_evidencia_inexistente(client: TestClient):
    response = client.delete("/evidencias/9999")
    assert response.status_code == 404


def test_filtrar_por_evento(client: TestClient):
    evento_id = _criar_evento(client)
    client.post(
        "/evidencias",
        json={"evento_id": evento_id, "tipo": "imagem", "url_externa": "https://exemplo.com/1.jpg"},
    )
    client.post(
        "/evidencias",
        json={"evento_id": evento_id, "tipo": "video", "url_externa": "https://exemplo.com/1.mp4"},
    )

    response = client.get(f"/evidencias?evento_id={evento_id}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filtrar_por_tipo(client: TestClient):
    evento_id = _criar_evento(client)
    client.post(
        "/evidencias",
        json={"evento_id": evento_id, "tipo": "imagem", "url_externa": "https://exemplo.com/a.jpg"},
    )

    response = client.get("/evidencias?tipo=imagem")
    assert response.status_code == 200
    assert all(e["tipo"] == "imagem" for e in response.json())
