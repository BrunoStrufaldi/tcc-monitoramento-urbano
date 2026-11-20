"""Testes das evidências. A rota só consulta, quem grava é a detecção."""

import hashlib

from fastapi.testclient import TestClient

from app.models.localizacao import Localizacao
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

    evento = detection_events.registrar_deteccao(
        db_session, deteccao, b"imagem-de-teste", -23.55052, -46.633308, endereco="Paulista - Av Brigadeiro Luiz Antônio",
    )

    assert evento.titulo == "Possível Trânsito detectado pelo YOLO"
    assert evento.tipo == "transito"
    assert evento.status == "em_analise"
    assert evento.localizacao.endereco == "Paulista - Av Brigadeiro Luiz Antônio"

    gravadas = client.get(f"/evidencias?evento_id={evento.id}").json()
    assert len(gravadas) == 1
    metadados = gravadas[0]["metadados"]
    assert (tmp_path / gravadas[0]["caminho_arquivo"]).is_file()
    assert (tmp_path / metadados["arquivo_original"]).read_bytes() == b"imagem-de-teste"
    assert metadados["sha256_original"] == hashlib.sha256(b"imagem-de-teste").hexdigest()
    assert metadados["validado_no_servidor"] is True


def test_atualizar_evento_troca_a_foto_e_mantem_o_numero(db_session, tmp_path, monkeypatch):
    """Ao ser confirmado de novo, o evento fica com uma foto só, a nova, e ganha o nome da câmera."""
    monkeypatch.setattr(detection_events, "_EVIDENCIAS_DIR", tmp_path)
    monkeypatch.setattr(detection_events, "annotate_evidence", lambda content, _detections: (content, 30, 40))
    deteccao = Deteccao(2, "transito", 0.91, "media", "transito", (1, 2, 30, 40))
    antigo = detection_events.registrar_deteccao(db_session, deteccao, b"imagem-velha", -23.5576, -46.6606)
    assert antigo.localizacao.endereco is None
    arquivo_velho = antigo.evidencias[0].caminho_arquivo

    encontrado = detection_events.buscar_evento_no_ponto(db_session, tipo="transito", latitude=-23.5576, longitude=-46.6606)
    assert encontrado is not None and encontrado.id == antigo.id

    analise = detection_events.Analise(
        deteccao=deteccao, fonte_nome="MotSP YOLO", fonte_descricao="teste",
        modelo_ia="YOLO11", origem="camera_continua_contagem",
        contexto=[("indice_congestionamento", 9.0, "indice_0_10")],
    )
    atualizado = detection_events.atualizar_evento(
        db_session, encontrado, analise, b"imagem-nova", endereco="Paulista - Av Brigadeiro Luiz Antônio",
    )

    assert atualizado.id == antigo.id
    assert atualizado.localizacao.endereco == "Paulista - Av Brigadeiro Luiz Antônio"
    assert len(atualizado.evidencias) == 1
    nova = atualizado.evidencias[0]
    assert (tmp_path / nova.metadados["arquivo_original"]).read_bytes() == b"imagem-nova"
    assert not (tmp_path / arquivo_velho).exists()
    assert [d.chave for d in atualizado.dados_contextuais] == ["indice_congestionamento"]


def test_eventos_antigos_ganham_o_nome_da_camera_pelo_ponto(db_session):
    """Ao iniciar, as localizações sem endereço no ponto de uma câmera recebem o nome dela."""
    na_camera = Localizacao(latitude=-23.5576, longitude=-46.6606)
    fora = Localizacao(latitude=-23.6000, longitude=-46.7000)
    db_session.add_all([na_camera, fora])
    db_session.commit()

    assert detection_events.preencher_enderecos_das_cameras(db_session) == 1
    assert na_camera.endereco == "Paulista - Av Brigadeiro Luiz Antônio"
    assert fora.endereco is None


def test_obter_arquivo_de_evidencia(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(evidencias, "_EVIDENCIAS_DIR", tmp_path)
    (tmp_path / "foto-teste.jpg").write_bytes(b"conteudo-fake-de-imagem")

    response = client.get("/evidencias/arquivo/foto-teste.jpg")
    assert response.status_code == 200
    assert response.content == b"conteudo-fake-de-imagem"
    assert client.get("/evidencias/arquivo/nao-existe.jpg").status_code == 404
