"""Testes da promoção/rebaixamento automático de status pelo Data Fusion.

Um evento YOLO só chega a "ativo" por promoção automática (a confirmação
humana cria "em_analise"); quando a confiabilidade não bate mais o limiar
``gx_fusion_auto_ativo_min`` ele deve voltar para "em_analise". Eventos
manuais (fonte não-YOLO) nunca são rebaixados."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models.evento import Evento
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.services import data_fusion_service
from data_fusion.models import ResultadoFusao


def _fixar_confiabilidade(monkeypatch, valor: float) -> None:
    def _fake(entrada):
        return ResultadoFusao(
            evento_id=entrada.evento_id,
            confiabilidade=valor,
            nivel="media",
            componentes=[],
        )

    monkeypatch.setattr(data_fusion_service, "calcular_confiabilidade", _fake)


def _criar_evento(db: Session, *, status: str, fonte_tipo: str) -> Evento:
    loc = Localizacao(latitude=-23.55, longitude=-46.63)
    db.add(loc)
    db.flush()
    fonte = FonteDados(nome=f"Fonte {fonte_tipo}", tipo=fonte_tipo)
    db.add(fonte)
    db.flush()
    evento = Evento(
        titulo="Trânsito detectado",
        tipo="transito",
        severidade="media",
        status=status,
        confianca=Decimal("0.90"),
        localizacao_id=loc.id,
        fonte_id=fonte.id,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


def test_evento_yolo_ativo_e_rebaixado_quando_abaixo_do_limiar(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min - 0.05)
    evento = _criar_evento(db_session, status="ativo", fonte_tipo="yolo")

    _, atualizado = data_fusion_service.aplicar_fusao_evento(
        db_session, evento.id, persistir=True
    )

    assert atualizado.status == "em_analise"


def test_evento_yolo_em_analise_e_promovido_quando_atinge_limiar(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min + 0.01)
    evento = _criar_evento(db_session, status="em_analise", fonte_tipo="yolo")

    _, atualizado = data_fusion_service.aplicar_fusao_evento(
        db_session, evento.id, persistir=True
    )

    assert atualizado.status == "ativo"


def test_evento_yolo_ativo_permanece_quando_acima_do_limiar(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min + 0.10)
    evento = _criar_evento(db_session, status="ativo", fonte_tipo="yolo")

    _, atualizado = data_fusion_service.aplicar_fusao_evento(
        db_session, evento.id, persistir=True
    )

    assert atualizado.status == "ativo"


def test_evento_manual_ativo_nao_e_rebaixado(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min - 0.20)
    evento = _criar_evento(db_session, status="ativo", fonte_tipo="operador")

    _, atualizado = data_fusion_service.aplicar_fusao_evento(
        db_session, evento.id, persistir=True
    )

    assert atualizado.status == "ativo"
