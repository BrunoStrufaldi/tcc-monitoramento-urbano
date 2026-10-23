from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_engine_kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 3600}
if settings.database_url.startswith("sqlite"):
    # As threads das câmeras gravam no banco junto com a API. Sem isso o SQLite
    # dá erro de banco travado em vez de esperar a vez.
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(settings.database_url, **_engine_kwargs)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _habilitar_wal(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
