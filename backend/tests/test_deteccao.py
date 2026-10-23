"""Testes das rotas de detecção YOLO (status e testador de imagem)."""

from fastapi.testclient import TestClient

from app.routers import deteccao
from ml.detector import Deteccao


def test_status_e_classes_do_detector(client: TestClient):
    classes = client.get("/deteccao/classes").json()["classes"]
    assert len(classes) == 6
    assert classes[0]["nome"] == "alagamento"

    status = client.get("/deteccao/status").json()
    assert status["modo"] in ("yolo", "indisponivel")
    assert isinstance(status["disponivel"], bool)


def test_upload_que_nao_e_imagem_retorna_400(client: TestClient):
    for rota in ("/deteccao/imagem", "/deteccao/incidente"):
        response = client.post(rota, files={"file": ("test.txt", b"not an image", "text/plain")})
        assert response.status_code == 400, rota


def test_incidente_imagem_retorna_deteccoes(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        deteccao,
        "detectar_incidentes_imagem",
        lambda _path, _threshold: [Deteccao(1, "alagamento", 0.9, "critica", "clima", (0, 0, 10, 10), "flood")],
    )
    response = client.post("/deteccao/incidente", files={"file": ("foto.jpg", b"imagem", "image/jpeg")})
    assert response.status_code == 200
    assert [d["nome"] for d in response.json()] == ["alagamento"]


def test_modelo_indisponivel_retorna_503(client: TestClient, monkeypatch):
    def _falha(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(deteccao, "detectar_imagem_real", _falha)
    monkeypatch.setattr(deteccao, "detectar_incidentes_imagem", _falha)
    for rota in ("/deteccao/imagem", "/deteccao/incidente"):
        response = client.post(rota, files={"file": ("frame.jpg", b"imagem", "image/jpeg")})
        assert response.status_code == 503, rota
