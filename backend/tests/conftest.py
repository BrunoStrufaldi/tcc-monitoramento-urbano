"""Fixtures compartilhadas pelos testes, com SQLite em memória."""

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registra todos os models no Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.localizacao import Localizacao

TEST_DATABASE_URL = "sqlite:///:memory:"
# Os testes nunca ligam o monitoramento, senão ele acessaria as câmeras de verdade.
settings.gx_monitoramento_ativo = False

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
    """Cliente de teste usando o banco de teste."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# --- Fábricas -----------------------------------------------------------
# O painel não tem rotas de criação, então os testes gravam os dados direto
# no banco, do mesmo jeito que a detecção faz.


@pytest.fixture
def criar_evento(db_session: Session):
    """Cria um evento (e a localização exigida pela FK) e devolve o objeto."""

    def _criar(**campos) -> Evento:
        localizacao = Localizacao(
            latitude=float(campos.pop("latitude", -23.5505)),
            longitude=float(campos.pop("longitude", -46.6333)),
            endereco=campos.pop("endereco", "Endereço de teste"),
        )
        db_session.add(localizacao)
        db_session.flush()

        campos.setdefault("titulo", "Evento de teste")
        campos.setdefault("tipo", "alagamento")
        if "confianca" in campos and campos["confianca"] is not None:
            campos["confianca"] = Decimal(str(campos["confianca"]))
        evento = Evento(localizacao_id=localizacao.id, **campos)
        db_session.add(evento)
        db_session.commit()
        db_session.refresh(evento)
        return evento

    return _criar


@pytest.fixture
def criar_evidencia(db_session: Session):
    """Cria uma evidência visual como a detecção grava."""

    def _criar(evento_id: int, **campos) -> EvidenciaVisual:
        campos.setdefault("tipo", "imagem")
        if "confianca" in campos and campos["confianca"] is not None:
            campos["confianca"] = Decimal(str(campos["confianca"]))
        evidencia = EvidenciaVisual(evento_id=evento_id, **campos)
        db_session.add(evidencia)
        db_session.commit()
        db_session.refresh(evidencia)
        return evidencia

    return _criar
