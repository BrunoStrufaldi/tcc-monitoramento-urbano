"""Fixtures compartilhadas para testes — usa SQLite em memória."""

from collections.abc import Generator
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — garante que todos os models registram no Base.metadata
from app.config import settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.usuario import Usuario
from app.security import create_access_token, hash_password

TEST_DATABASE_URL = "sqlite:///:memory:"
settings.auth_secret_key = secrets.token_urlsafe(32)
# Nunca deixa o .env local ligar as threads de monitoramento contínuo durante
# os testes — elas fariam chamadas de rede reais (câmera CET) a cada
# TestClient criado.
settings.gx_monitoramento_ativo = False
TEST_PASSWORD_HASH = hash_password("senha-de-teste-segura")

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Habilita foreign keys no SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Cria tabelas, fornece sessão e faz drop no final."""
    Base.metadata.create_all(bind=engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient com override de dependência de banco."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    admin = Usuario(nome_usuario="admin-test", senha_hash=TEST_PASSWORD_HASH, perfil="administrador")
    db_session.add(admin)
    db_session.commit()
    token, _ = create_access_token(admin)
    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        c.headers.update({"Authorization": "Bearer " + token})
        yield c
    fastapi_app.dependency_overrides.clear()
