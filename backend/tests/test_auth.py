from app.config import settings
from app.models.auditoria_acao import AuditoriaAcao
from app.models.usuario import Usuario
from app.security import create_access_token, hash_password

_TEST_HASH = hash_password("senha-de-teste-segura")


def _operator_token(db_session):
    user = Usuario(nome_usuario="operador-test", senha_hash=_TEST_HASH, perfil="operador")
    db_session.add(user)
    db_session.commit()
    token, _ = create_access_token(user)
    return user, {"Authorization": "Bearer " + token}


def test_login_retorna_token_com_expiracao(client):
    response = client.post("/auth/login", json={"nome_usuario": "admin-test", "senha": "senha-de-teste-segura"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] > 0


def test_operador_pode_alterar_status_do_evento(client, db_session):
    _, headers = _operator_token(db_session)
    created = client.post("/eventos", json={
        "titulo": "Evento para auditoria",
        "tipo": "transito",
        "latitude": -23.55,
        "longitude": -46.63,
    })
    evento_id = created.json()["id"]

    response = client.patch(f"/eventos/{evento_id}", json={"status": "em_analise"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "em_analise"
    audit = db_session.query(AuditoriaAcao).filter(AuditoriaAcao.evento_id == evento_id, AuditoriaAcao.acao == "EVENTO_ATUALIZAR").one()
    assert audit.resultado == "sucesso"


def test_operador_nao_pode_criar_usuario(client, db_session):
    _, headers = _operator_token(db_session)

    response = client.post("/auth/usuarios", json={"nome_usuario": "bloqueado", "senha": "senha-de-teste-segura", "perfil": "administrador"}, headers=headers)

    assert response.status_code == 403
    assert db_session.query(AuditoriaAcao).filter(AuditoriaAcao.resultado == "negado").count() == 1


def test_token_expirado_e_negado(client, db_session):
    user, _ = _operator_token(db_session)
    previous = settings.auth_token_expire_minutes
    settings.auth_token_expire_minutes = -1
    try:
        expired_token, _ = create_access_token(user)
    finally:
        settings.auth_token_expire_minutes = previous

    response = client.get("/eventos", headers={"Authorization": "Bearer " + expired_token})

    assert response.status_code == 401
