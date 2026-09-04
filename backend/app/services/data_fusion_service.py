import sys
from decimal import ROUND_HALF_UP, Decimal
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

_CENTESIMO = Decimal("0.01")


def atinge_limiar_ativo(confiabilidade: float) -> bool:
    """Decide pela confiabilidade **exibida**, não pelo float cru.

    A interface mostra a confiabilidade como percentual inteiro, então um
    evento de 0.7977 aparece como "80%" — e a regra "80% na tela vira ativo"
    mentia, porque 0.7977 < 0.80. Arredondar antes de comparar alinha a
    decisão ao número que o operador vê. ROUND_HALF_UP sobre a representação
    decimal do float reproduz o critério do Intl.NumberFormat usado no front
    (ver ``atingeLimiarAtivo`` em frontend/src/fusion-format.ts); o limiar
    entra cru, para que um valor configurado entre centésimos continue valendo
    exatamente o que foi configurado.
    """
    exibida = Decimal(str(confiabilidade)).quantize(_CENTESIMO, rounding=ROUND_HALF_UP)
    return exibida >= Decimal(str(settings.gx_fusion_auto_ativo_min))


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
        atinge = atinge_limiar_ativo(resultado.confiabilidade)
        automatico = bool(evento.fonte and evento.fonte.tipo == "yolo")
        promovido = False
        rebaixado = False
        if evento.status == "em_analise" and atinge:
            evento.status = "ativo"
            promovido = True
        elif (
            evento.status == "ativo"
            and automatico
            and not atinge
        ):
            # Evento YOLO só chega a "ativo" por promoção automática (a
            # confirmação humana cria "em_analise"). Se a confiabilidade não
            # bate mais o limiar, volta para análise em vez de ficar preso.
            evento.status = "em_analise"
            rebaixado = True
        mudou_status = promovido or rebaixado
        log = LogSistema(
            nivel="INFO",
            modulo="data_fusion",
            mensagem=(
                f"Confiabilidade recalculada: {resultado.confiabilidade:.2%} ({resultado.nivel})"
                + (" — evento promovido para ativo" if promovido else "")
                + (" — evento rebaixado para em análise" if rebaixado else "")
            ),
            evento_id=evento.id,
            contexto={
                "confiabilidade": resultado.confiabilidade,
                "nivel": resultado.nivel,
                "promovido_para_ativo": promovido,
                "rebaixado_para_analise": rebaixado,
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
        if mudou_status:
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
    """Recalcula os eventos automáticos abertos (em análise ou ativos) e ajusta
    o status ao limiar de confiabilidade: promove os que já batem e rebaixa os
    que deixaram de bater (ex.: limiar elevado, dado de clima que chegou depois).
    Rede de segurança para o que só mudaria num recálculo posterior."""
    ids = [
        row[0]
        for row in db.query(Evento.id).filter(Evento.status.in_(("em_analise", "ativo"))).all()
    ]
    ajustados = 0
    for evento_id in ids:
        try:
            antes = db.query(Evento.status).filter(Evento.id == evento_id).scalar()
            _, evento = aplicar_fusao_evento(db, evento_id, persistir=True)
            if evento.status != antes:
                ajustados += 1
        except ValueError:
            continue
    return ajustados
