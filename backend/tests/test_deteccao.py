"""Testes das rotas de consulta da detecção YOLO."""

from fastapi.testclient import TestClient


def test_status_e_classes_do_detector(client: TestClient):
    classes = client.get("/deteccao/classes").json()["classes"]
    assert len(classes) == 6
    assert classes[0]["nome"] == "alagamento"

    status = client.get("/deteccao/status").json()
    assert status["modo"] in ("yolo", "indisponivel")
    assert isinstance(status["disponivel"], bool)

    cameras = client.get("/deteccao/cameras").json()
    assert len(cameras) == 10
    assert set(cameras[0]) == {"id", "nome", "latitude", "longitude"}


def test_rotas_de_upload_foram_removidas(client: TestClient):
    # O testador de imagens saiu do painel e as rotas dele também.
    for rota in ("/deteccao/imagem", "/deteccao/incidente"):
        response = client.post(rota, files={"file": ("frame.jpg", b"imagem", "image/jpeg")})
        assert response.status_code in (404, 405), rota
