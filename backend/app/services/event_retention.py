"""Apaga eventos do banco e do painel.

O painel mostra só o que está acontecendo agora. Quem decide apagar um evento é
o ciclo de monitoramento, quando a câmera passa dois ciclos sem confirmar o
evento. O evento sai junto com as evidências e os dados ligados a ele, e cada
remoção é avisada ao painel, para ele tirar o evento da tela.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broadcast import schedule_coroutine
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.localizacao import Localizacao
from app.models.log_sistema import LogSistema
from app.routers.tempo_real import _broadcast
from app.ws_manager import manager as ws_manager


def limite_da_janela(janela_minutos: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=janela_minutos)


def _publicar_remocoes(ids: list[int]) -> None:
    for evento_id in ids:
        payload = {"id": evento_id}
        schedule_coroutine(_broadcast("evento_removido", payload))
        schedule_coroutine(ws_manager.broadcast_evento("evento_removido", payload))


def _apagar_eventos(db: Session, ids: list[int]) -> None:
    if not ids:
        return
    localizacao_ids = list(db.scalars(select(Evento.localizacao_id).where(Evento.id.in_(ids))))
    db.query(EvidenciaVisual).filter(EvidenciaVisual.evento_id.in_(ids)).delete(synchronize_session=False)
    db.query(DadoContextual).filter(DadoContextual.evento_id.in_(ids)).delete(synchronize_session=False)
    db.query(LogSistema).filter(LogSistema.evento_id.in_(ids)).update(
        {LogSistema.evento_id: None}, synchronize_session=False
    )
    db.query(Evento).filter(Evento.id.in_(ids)).delete(synchronize_session=False)
    if localizacao_ids:
        ainda_usadas = set(db.scalars(select(Evento.localizacao_id).where(Evento.localizacao_id.in_(localizacao_ids))))
        orfas = [lid for lid in set(localizacao_ids) if lid and lid not in ainda_usadas]
        if orfas:
            db.query(Localizacao).filter(Localizacao.id.in_(orfas)).delete(synchronize_session=False)
    db.commit()
    _publicar_remocoes(ids)


def remover_eventos(db: Session, ids: list[int]) -> None:
    """Apaga eventos escolhidos e tira eles do painel."""
    _apagar_eventos(db, ids)


def colapsar_eventos_duplicados(db: Session) -> int:
    """Deixa só o evento mais recente de cada tipo em cada ponto."""
    vivos = (
        db.query(Evento.id, Evento.tipo, Evento.detectado_em, Localizacao.latitude, Localizacao.longitude)
        .join(Localizacao, Evento.localizacao_id == Localizacao.id)
        .filter(Evento.status.in_(("em_analise", "ativo")))
        .all()
    )
    melhor: dict[tuple, tuple[int, object]] = {}
    perdedores: list[int] = []
    for eid, tipo, detectado_em, lat, lng in vivos:
        chave = (tipo, round(float(lat), 5), round(float(lng), 5))
        atual = melhor.get(chave)
        if atual is None or detectado_em > atual[1]:
            if atual is not None:
                perdedores.append(atual[0])
            melhor[chave] = (eid, detectado_em)
        else:
            perdedores.append(eid)
    _apagar_eventos(db, perdedores)
    return len(perdedores)
