"""Testes da mudança automática de status pelo Data Fusion.

O evento do YOLO só vira ativo quando passa do limite de confiabilidade, e
volta para análise se cair abaixo dele. Eventos que não vêm do YOLO nunca voltam.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.evento import Evento
from app.models.fonte_dados import FonteDados
from app.models.localizacao import Localizacao
from app.models.log_sistema import LogSistema
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


def test_evento_yolo_e_promovido_ao_atingir_o_limiar(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min + 0.01)
    evento = _criar_evento(db_session, status="em_analise", fonte_tipo="yolo")

    _, atualizado = data_fusion_service.aplicar_fusao_evento(db_session, evento.id, persistir=True)

    assert atualizado.status == "ativo"
    logs = db_session.query(LogSistema).filter(LogSistema.evento_id == evento.id).all()
    assert len(logs) == 1
    assert logs[0].contexto["promovido_para_ativo"] is True

    # Se o status não muda, não grava log, porque o recálculo roda o tempo todo.
    _, atualizado = data_fusion_service.aplicar_fusao_evento(db_session, evento.id, persistir=True)
    assert atualizado.status == "ativo"
    assert db_session.query(LogSistema).filter(LogSistema.evento_id == evento.id).count() == 1


def test_evento_yolo_e_rebaixado_abaixo_do_limiar_mas_o_manual_nao(db_session: Session, monkeypatch):
    _fixar_confiabilidade(monkeypatch, settings.gx_fusion_auto_ativo_min - 0.05)
    yolo = _criar_evento(db_session, status="ativo", fonte_tipo="yolo")
    manual = _criar_evento(db_session, status="ativo", fonte_tipo="operador")

    _, yolo = data_fusion_service.aplicar_fusao_evento(db_session, yolo.id, persistir=True)
    _, manual = data_fusion_service.aplicar_fusao_evento(db_session, manual.id, persistir=True)

    assert yolo.status == "em_analise"
    assert manual.status == "ativo"


def test_limiar_compara_o_percentual_arredondado(db_session: Session, monkeypatch):
    """0,7977 aparece como 80% no painel e vira ativo. 0,7949 aparece como 79% e não vira."""
    monkeypatch.setattr(settings, "gx_fusion_auto_ativo_min", 0.80)
    for valor, esperado in ((0.7977, "ativo"), (0.7949, "em_analise")):
        _fixar_confiabilidade(monkeypatch, valor)
        evento = _criar_evento(db_session, status="em_analise", fonte_tipo="yolo")
        _, atualizado = data_fusion_service.aplicar_fusao_evento(db_session, evento.id, persistir=True)
        assert atualizado.status == esperado, valor


def test_migrar_categoria_legada_mantem_contexto_do_evento(db_session: Session):
    """Dado gravado com a categoria antiga ("clima") continua entrando na fusão."""
    from app.models.dado_contextual import DadoContextual

    evento = _criar_evento(db_session, status="em_analise", fonte_tipo="yolo")
    db_session.add(DadoContextual(evento_id=evento.id, categoria="clima", chave="indice_congestionamento", valor_numerico=8.0))
    db_session.add(DadoContextual(evento_id=evento.id, categoria="outra", chave="x", valor_numerico=1.0))
    db_session.commit()

    assert data_fusion_service.migrar_categoria_legada(db_session) == 1
    assert data_fusion_service.migrar_categoria_legada(db_session) == 0  # rodar de novo não muda nada

    entrada = data_fusion_service.evento_para_fusao(db_session.get(Evento, evento.id))
    assert [d.chave for d in entrada.dados_contexto] == ["indice_congestionamento"]
