"""Testes do módulo de detecção YOLO (simulado)."""

from fastapi.testclient import TestClient


def test_listar_classes(client: TestClient):
    response = client.get("/deteccao/classes")
    assert response.status_code == 200
    data = response.json()
    assert "classes" in data
    assert len(data["classes"]) == 8
    assert data["classes"][0]["nome"] == "buraco"


def test_simular_deteccao(client: TestClient):
    response = client.post("/deteccao/simular")
    assert response.status_code == 200
    deteccoes = response.json()
    assert isinstance(deteccoes, list)
    assert 1 <= len(deteccoes) <= 3
    for d in deteccoes:
        assert "classe_id" in d
        assert "nome" in d
        assert 0 <= d["confianca"] <= 1
        assert d["severidade"] in ("baixa", "media", "alta", "critica")


def test_simular_com_quantidade(client: TestClient):
    response = client.post("/deteccao/simular", json={"num_deteccoes": 5})
    assert response.status_code == 200
    deteccoes = response.json()
    assert len(deteccoes) == 5


def test_detectar_em_video(client: TestClient):
    response = client.post("/deteccao/video", params={"num_frames": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["total_frames"] == 10
    assert data["total_deteccoes"] >= 0
    assert "resumo_classes" in data


def test_imagem_invalida_rejeitada(client: TestClient):
    response = client.post(
        "/deteccao/imagem",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
