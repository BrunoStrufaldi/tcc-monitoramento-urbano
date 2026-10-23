"""Testes das evidências. A rota só consulta, quem grava é a detecção."""

import hashlib

from fastapi.testclient import TestClient

from app.routers import evidencias
from app.services import detection_events
from ml.detector import Deteccao


def test_registrar_deteccao_grava_evento_e_evidencia_auditavel(client: TestClient, db_session, tmp_path, monkeypatch):
    """A detecção cria o evento em análise, com a imagem marcada, a original e o hash dela."""
    # A rota precisa ler as evidências da mesma pasta onde a detecção grava.
    assert evidencias._EVIDENCIAS_DIR == detection_events._EVIDENCIAS_DIR

    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 30, 40))
    deteccao = Deteccao(2, "transito", 0.91, "media", "transito", (1, 2, 30, 40))

    evento = detection_events.registrar_deteccao(db_session, deteccao, b"imagem-de-teste", -23.55052, -46.633308)

    assert evento.titulo == "Possível Trânsito detectado pelo YOLO"
    assert evento.tipo == "transito"
    assert evento.status == "em_analise"

    gravadas = client.get(f"/evidencias?evento_id={evento.id}").json()
    assert len(gravadas) == 1
    metadados = gravadas[0]["metadados"]
    assert (tmp_path / gravadas[0]["caminho_arquivo"]).is_file()
    assert (tmp_path / metadados["arquivo_original"]).read_bytes() == b"imagem-de-teste"
    assert metadados["sha256_original"] == hashlib.sha256(b"imagem-de-teste").hexdigest()
    assert metadados["validado_no_servidor"] is True


def test_obter_arquivo_de_evidencia(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(evidencias, "_EVIDENCIAS_DIR", tmp_path)
    (tmp_path / "foto-teste.jpg").write_bytes(b"conteudo-fake-de-imagem")

    response = client.get("/evidencias/arquivo/foto-teste.jpg")
    assert response.status_code == 200
    assert response.content == b"conteudo-fake-de-imagem"
    assert client.get("/evidencias/arquivo/nao-existe.jpg").status_code == 404
