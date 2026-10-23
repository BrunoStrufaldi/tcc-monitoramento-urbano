"""Testes da limpeza de eventos antigos.

Todo evento apagado do banco também precisa sair do painel.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.evento import Evento
from app.models.localizacao import Localizacao
from app.services import event_retention


@pytest.fixture
def remocoes_publicadas(monkeypatch) -> list[tuple[str, dict]]:
    publicadas: list[tuple[str, dict]] = []

    def _fake_schedule(coro):
        coro.close()  # não há loop rodando no teste; evita "never awaited"

    monkeypatch.setattr(event_retention, "schedule_coroutine", _fake_schedule)
    monkeypatch.setattr(
        event_retention,
        "_broadcast",
        lambda tipo, dados: publicadas.append((tipo, dados)) or _noop(),
    )
    monkeypatch.setattr(
        event_retention.ws_manager,
        "broadcast_evento",
        lambda tipo, dados: _noop(),
    )
    return publicadas


async def _noop() -> None:
    return None


def _criar_evento(db: Session, *, tipo: str, minutos_atras: float, lat: float, lng: float) -> int:
    localizacao = Localizacao(latitude=lat, longitude=lng)
    db.add(localizacao)
    db.flush()
    evento = Evento(
        titulo="Evento " + tipo,
        tipo=tipo,
        severidade="media",
        status="em_analise",
        localizacao_id=localizacao.id,
        detectado_em=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=minutos_atras),
    )
    db.add(evento)
    db.commit()
    return evento.id


def test_purga_remove_so_o_antigo_e_avisa_o_painel(db_session: Session, remocoes_publicadas) -> None:
    antigo = _criar_evento(db_session, tipo="transito", minutos_atras=90, lat=-23.55, lng=-46.63)
    recente = _criar_evento(db_session, tipo="transito", minutos_atras=1, lat=-23.56, lng=-46.64)

    assert event_retention.purgar_eventos_expirados(db_session, janela_minutos=45) == 1
    assert event_retention.purgar_eventos_expirados(db_session, janela_minutos=45) == 0

    assert db_session.get(Evento, antigo) is None
    assert db_session.get(Evento, recente) is not None
    assert remocoes_publicadas == [("evento_removido", {"id": antigo})]


def test_colapso_junta_repetidos_e_avisa_o_painel(db_session: Session, remocoes_publicadas) -> None:
    velho = _criar_evento(db_session, tipo="transito", minutos_atras=10, lat=-23.55, lng=-46.63)
    novo = _criar_evento(db_session, tipo="transito", minutos_atras=1, lat=-23.55, lng=-46.63)

    assert event_retention.colapsar_eventos_duplicados(db_session) == 1
    assert event_retention.colapsar_eventos_duplicados(db_session) == 0

    assert db_session.get(Evento, velho) is None
    assert db_session.get(Evento, novo) is not None
    assert remocoes_publicadas == [("evento_removido", {"id": velho})]
