import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.config import settings
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
        promovido = False
        if (
            evento.status == "em_analise"
            and resultado.confiabilidade >= settings.gx_fusion_auto_ativo_min
        ):
            evento.status = "ativo"
            promovido = True
        log = LogSistema(
            nivel="INFO",
            modulo="data_fusion",
            mensagem=(
                f"Confiabilidade recalculada: {resultado.confiabilidade:.2%} ({resultado.nivel})"
                + (" — evento promovido para ativo" if promovido else "")
            ),
            evento_id=evento.id,
            contexto={
                "confiabilidade": resultado.confiabilidade,
                "nivel": resultado.nivel,
                "promovido_para_ativo": promovido,
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
        if promovido:
            _publicar_evento_atualizado(db, evento.id)

    return resultado, evento


def _publicar_evento_atualizado(db: Session, evento_id: int) -> None:
    """Import tardio para evitar ciclo com detection_events."""
    try:
        from app.services.detection_events import publicar_evento

        publicar_evento(db, evento_id)
    except Exception:
        pass


def promover_eventos_por_confiabilidade(db: Session) -> int:
    """Recalcula os eventos ainda em análise e promove os que já batem o
    limiar de confiabilidade. Rede de segurança para eventos que só passariam
    a "ativo" num recálculo posterior (ex.: dado de clima que chegou depois)."""
    ids = [row[0] for row in db.query(Evento.id).filter(Evento.status == "em_analise").all()]
    promovidos = 0
    for evento_id in ids:
        try:
            _, evento = aplicar_fusao_evento(db, evento_id, persistir=True)
            if evento.status == "ativo":
                promovidos += 1
        except ValueError:
            continue
    return promovidos
