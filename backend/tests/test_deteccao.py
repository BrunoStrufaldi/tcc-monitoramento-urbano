"""Testes das rotas de detecção YOLO (status e testador de imagem)."""

from fastapi.testclient import TestClient


def test_listar_classes(client: TestClient):
    response = client.get("/deteccao/classes")
    assert response.status_code == 200
    data = response.json()
    assert "classes" in data
    assert len(data["classes"]) == 6
    assert data["classes"][0]["nome"] == "alagamento"


def test_status_detector_explica_o_modo_ativo(client: TestClient):
    response = client.get("/deteccao/status")
    assert response.status_code == 200
    data = response.json()
    assert data["modo"] in ("yolo", "indisponivel")
    assert isinstance(data["disponivel"], bool)


def test_imagem_invalida_rejeitada(client: TestClient):
    response = client.post(
        "/deteccao/imagem",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_incidente_imagem_invalida_rejeitada(client: TestClient):
    response = client.post(
        "/deteccao/incidente",
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


def test_incidente_imagem_retorna_deteccoes(client: TestClient, monkeypatch):
    from app.routers import deteccao
    from ml.detector import Deteccao

    monkeypatch.setattr(
        deteccao,
        "detectar_incidentes_imagem",
        lambda _path, _threshold: [Deteccao(1, "alagamento", 0.9, "critica", "clima", (0, 0, 10, 10), "flood")],
    )
    response = client.post(
        "/deteccao/incidente",
        files={"file": ("foto.jpg", b"imagem", "image/jpeg")},
    )
    assert response.status_code == 200
    deteccoes = response.json()
    assert len(deteccoes) == 1
    assert deteccoes[0]["nome"] == "alagamento"


def test_incidente_modelo_indisponivel_retorna_503(client: TestClient, monkeypatch):
    from app.routers import deteccao

    def _fail(_path, _threshold):
        raise RuntimeError("modelo de incidentes indisponível")

    monkeypatch.setattr(deteccao, "detectar_incidentes_imagem", _fail)
    response = client.post(
        "/deteccao/incidente",
        files={"file": ("foto.jpg", b"imagem", "image/jpeg")},
    )
    assert response.status_code == 503


def test_imagem_modelo_indisponivel_retorna_503(client: TestClient, monkeypatch):
    from app.routers import deteccao

    def _fail(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(deteccao, "detectar_imagem_real", _fail)
    response = client.post(
        "/deteccao/imagem",
        files={"file": ("frame.jpg", b"imagem", "image/jpeg")},
    )
    assert response.status_code == 503


def test_rotas_que_gravavam_pelo_painel_nao_existem(client: TestClient):
    """O painel é somente leitura: nenhuma rota de detecção cria evento."""
    for rota in ("/deteccao/confirmar", "/deteccao/frame", "/deteccao/simular", "/deteccao/video"):
        # 405 quando o painel está montado em "/" (StaticFiles só aceita GET).
        assert client.post(rota).status_code in (404, 405)
