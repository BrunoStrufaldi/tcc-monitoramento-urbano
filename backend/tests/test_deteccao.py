"""Testes do módulo de detecção YOLO (simulado)."""

from fastapi.testclient import TestClient


def test_listar_classes(client: TestClient):
    response = client.get("/deteccao/classes")
    assert response.status_code == 200
    data = response.json()
    assert "classes" in data
    assert len(data["classes"]) == 7
    assert data["classes"][0]["nome"] == "alagamento"


def test_status_detector_explica_o_modo_ativo(client: TestClient):
    response = client.get("/deteccao/status")
    assert response.status_code == 200
    data = response.json()
    assert data["modo"] in ("yolo", "simulacao")
    assert isinstance(data["disponivel"], bool)


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


def test_falha_de_modelo_retorna_indisponivel(client: TestClient, monkeypatch):
    from app.routers import deteccao

    def _fail(_path, _threshold):
        raise RuntimeError("modelo indisponível")

    monkeypatch.setattr(deteccao.visual_validation_service, "_detector", _fail)
    response = client.post(
        "/deteccao/frame",
        files={"file": ("frame.jpg", b"imagem", "image/jpeg")},
        data={"frame_id": "falha-1"},
    )
    assert response.status_code == 503


def test_confirmar_deteccao_cria_evento_e_evidencia(client: TestClient, tmp_path, monkeypatch):
    """A confirmação manual preserva evidência e cria um evento auditável."""
    from app.routers import deteccao
    from app.services import detection_events
    from ml.detector import Deteccao

    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(
        deteccao.visual_validation_service,
        "_detector",
        lambda _path, _threshold: [Deteccao(8, "veiculo", 0.91, "baixa", "observacao_visual", (1, 2, 30, 40), "car")],
    )
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 30, 40))
    deteccao.visual_validation_service._recent.clear()
    response = client.post(
        "/deteccao/confirmar",
        files={"file": ("captura.jpg", b"imagem-de-teste", "image/jpeg")},
        data={
            "nome": "veiculo",
            "confianca": "0.91",
            "severidade": "media",
            "tipo": "mobilidade",
            "latitude": "-23.55052",
            "longitude": "-46.633308",
        },
    )
    assert response.status_code == 201
    evento = response.json()
    assert evento["titulo"] == "Observação YOLO: Veículo detectado"
    assert evento["tipo"] == "observacao_visual"
    assert evento["status"] == "em_analise"
    assert evento["severidade"] == "baixa"

    evidencias = client.get(f"/evidencias?evento_id={evento['id']}").json()
    assert len(evidencias) == 1
    arquivo = evidencias[0]["caminho_arquivo"]
    assert (tmp_path / arquivo).is_file()
    assert evidencias[0]["metadados"]["validado_no_servidor"] is True
