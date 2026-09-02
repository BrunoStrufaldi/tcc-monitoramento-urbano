"""Retenção de eventos em tempo real.

O painel do MotSP é um quadro operacional "ao vivo": um evento só faz sentido
enquanto a detecção que o originou é recente. Este módulo apaga em definitivo
tudo que passou da janela (``GX_EVENTO_JANELA_MINUTOS``) — evento, evidências,
dados contextuais, notificações e a localização 1:1 criada para ele.

Toda remoção é propagada como ``evento_removido`` em WS/SSE: o painel só tira um
evento da lista quando recebe essa mensagem, então apagar em silêncio deixava
cópias fantasma acumulando na tela (contador acima do que existe no banco).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.broadcast import schedule_coroutine
from app.config import settings
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.evidencia_visual import EvidenciaVisual
from app.models.localizacao import Localizacao
from app.models.log_sistema import LogSistema
from app.models.notificacao import Notificacao
from app.routers.tempo_real import _broadcast
from app.ws_manager import manager as ws_manager


def limite_da_janela(janela_minutos: int | None = None) -> datetime:
    minutos = settings.gx_evento_janela_minutos if janela_minutos is None else janela_minutos
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=minutos)


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
    db.query(Notificacao).filter(Notificacao.evento_id.in_(ids)).delete(synchronize_session=False)
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


def colapsar_eventos_duplicados(db: Session) -> int:
    """Mantém, por (tipo + ponto ~5 casas), apenas o evento mais recente.

    Rede de segurança para pilhas criadas antes do dedup em ``detection_events``
    (ex.: reinícios seguidos do servidor zerando o cooldown em memória).
    """
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


def purgar_eventos_expirados(db: Session, janela_minutos: int | None = None) -> int:
    """Remove eventos detectados antes da janela. Retorna quantos foram apagados."""
    minutos = settings.gx_evento_janela_minutos if janela_minutos is None else janela_minutos
    if minutos <= 0:
        return 0

    corte = limite_da_janela(minutos)
    ids = list(db.scalars(select(Evento.id).where(Evento.detectado_em < corte)))
    _apagar_eventos(db, ids)
    return len(ids)
