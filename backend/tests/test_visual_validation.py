from app.models.evidencia_visual import EvidenciaVisual
from app.models.evento import Evento
from app.models.localizacao import Localizacao
from app.services.visual_validation import VisualValidationService, visual_validation_service
from ml.detector import Deteccao


def _detector(_path, _threshold):
    return [Deteccao(2, "transito", 0.8, "media", "mobilidade", (1, 2, 30, 40))]


def test_detector_simulado_respeita_threshold():
    service = VisualValidationService(detector=_detector)
    result = service.simulate_frame("sim-1", threshold=0.99)
    assert result.deteccoes == []


def test_frame_valido_e_deduplicado():
    service = VisualValidationService(detector=_detector, now=lambda: 10.0)
    first = service.validate_frame(b"bytes", "image/jpeg", "frame-1", 0.5)
    second = service.validate_frame(b"bytes", "image/jpeg", "frame-2", 0.5)
    assert first.relevante is True
    assert second.deteccoes[0].duplicada is True


def test_frame_invalido_rejeitado():
    service = VisualValidationService(detector=_detector)
    try:
        service.validate_frame(b"bytes", "text/plain", "frame-1")
    except ValueError as exc:
        assert "Formato inválido" in str(exc)
    else:
        assert False, "MIME inválido deveria falhar"


def test_frame_persistido_cria_evidencia_e_recalcula_fusao(client, db_session, monkeypatch):
    monkeypatch.setattr(visual_validation_service, "_detector", _detector)
    visual_validation_service._recent.clear()
    location = Localizacao(latitude=-23.55, longitude=-46.63)
    db_session.add(location)
    db_session.flush()
    event = Evento(titulo="Evento", tipo="mobilidade", localizacao_id=location.id)
    db_session.add(event)
    db_session.commit()

    response = client.post("/deteccao/frame", files={"file": ("frame.jpg", b"bytes", "image/jpeg")}, data={"frame_id": "frame-1", "threshold": "0.5", "evento_id": str(event.id), "persistir": "true"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidencia_id"]
    assert payload["confianca_fusion"] is not None
    assert db_session.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id == event.id).count() == 1


def test_frame_websocket(client, monkeypatch):
    monkeypatch.setattr(visual_validation_service, "_detector", _detector)
    visual_validation_service._recent.clear()
    import base64
    with client.websocket_connect("/ws/cv") as socket:
        assert socket.receive_json()["tipo"] == "pronto"
        socket.send_json({"tipo": "frame", "frame_id": "ws-1", "mime": "image/jpeg", "conteudo": base64.b64encode(b"bytes").decode(), "threshold": 0.5})
        assert socket.receive_json()["tipo"] == "frame_resultado"
