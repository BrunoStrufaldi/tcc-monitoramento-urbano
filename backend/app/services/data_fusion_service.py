import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.models.evento import Evento
from app.models.log_sistema import LogSistema

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_fusion.fusion import calcular_confiabilidade  # noqa: E402
from data_fusion.models import (  # noqa: E402
    DadoClima,
    EvidenciaIA,
    EventoFusionInput,
    FonteInfo,
    ResultadoFusao,
)

_FUSION_LOAD = (
    joinedload(Evento.fonte),
    joinedload(Evento.evidencias),
    joinedload(Evento.dados_contextuais),
)


def _buscar_evento(db: Session, evento_id: int) -> Evento | None:
    return (
        db.query(Evento)
        .options(*_FUSION_LOAD)
        .filter(Evento.id == evento_id)
        .first()
    )


def evento_para_fusao(evento: Evento) -> EventoFusionInput:
    evidencias = [
        EvidenciaIA(
            confianca=float(e.confianca) if e.confianca is not None else None,
            modelo_ia=e.modelo_ia,
            classe_detectada=e.classe_detectada,
        )
        for e in evento.evidencias
    ]

    dados_clima = [
        DadoClima(
            chave=d.chave,
            valor_numerico=d.valor_numerico,
            unidade=d.unidade,
        )
        for d in evento.dados_contextuais
        if d.categoria.lower() == "clima"
    ]

    fonte = None
    if evento.fonte:
        fonte = FonteInfo(
            tipo=evento.fonte.tipo,
            nome=evento.fonte.nome,
            ativo=bool(evento.fonte.ativo),
        )

    return EventoFusionInput(
        evento_id=evento.id,
        tipo=evento.tipo,
        evidencias_ia=evidencias,
        dados_clima=dados_clima,
        fonte=fonte,
    )


def aplicar_fusao_evento(
    db: Session,
    evento_id: int,
    *,
    persistir: bool = False,
) -> tuple[ResultadoFusao, Evento]:
    evento = _buscar_evento(db, evento_id)
    if not evento:
        raise ValueError(f"Evento {evento_id} não encontrado")

    entrada = evento_para_fusao(evento)
    resultado = calcular_confiabilidade(entrada)

    if persistir:
        evento.confianca = Decimal(str(resultado.confiabilidade))
        log = LogSistema(
            nivel="INFO",
            modulo="data_fusion",
            mensagem=f"Confiabilidade recalculada: {resultado.confiabilidade:.2%} ({resultado.nivel})",
            evento_id=evento.id,
            contexto={
                "confiabilidade": resultado.confiabilidade,
                "nivel": resultado.nivel,
                "componentes": [
                    {
                        "nome": c.nome,
                        "pontuacao": c.pontuacao,
                        "contribuicao": c.contribuicao,
                    }
                    for c in resultado.componentes
                ],
            },
        )
        db.add(log)
        db.commit()
        db.refresh(evento)

    return resultado, evento
