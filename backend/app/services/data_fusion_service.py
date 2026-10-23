import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.dado_contextual import DadoContextual
from app.models.evento import Evento
from app.models.log_sistema import LogSistema

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_fusion.fusion import calcular_confiabilidade  # noqa: E402
from data_fusion.models import (  # noqa: E402
    DadoContexto,
    EvidenciaIA,
    EventoFusionInput,
    ResultadoFusao,
)

_CENTESIMO = Decimal("0.01")

# Categoria dos dados que entram na dimensão de contexto do Data Fusion.
CATEGORIA_CONTEXTO = "contexto"


def migrar_categoria_legada(db: Session) -> int:
    """Troca o nome antigo da categoria ("clima") nos dados já gravados.

    Roda quando o sistema inicia e pode rodar várias vezes sem problema.
    """
    alterados = (
        db.query(DadoContextual)
        .filter(DadoContextual.categoria == "clima")
        .update({"categoria": CATEGORIA_CONTEXTO}, synchronize_session=False)
    )
    db.commit()
    return alterados


def atinge_limiar_ativo(confiabilidade: float) -> bool:
    """Compara a confiabilidade arredondada, do mesmo jeito que aparece na tela.

    Assim um evento que aparece como 80% no painel é tratado como 80% também
    aqui, mesmo que o valor exato seja 79,77%.
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

    dados_contexto = [
        DadoContexto(
            chave=d.chave,
            valor_numerico=d.valor_numerico,
            unidade=d.unidade,
        )
        for d in evento.dados_contextuais
        if d.categoria.lower() == CATEGORIA_CONTEXTO
    ]

    return EventoFusionInput(
        evento_id=evento.id,
        tipo=evento.tipo,
        evidencias_ia=evidencias,
        dados_contexto=dados_contexto,
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
            # Se a confiabilidade caiu abaixo do limite, o evento volta para análise.
            evento.status = "em_analise"
            rebaixado = True
        mudou_status = promovido or rebaixado
        if mudou_status:
            # Só registra no log quando o status muda.
            db.add(
                LogSistema(
                    nivel="INFO",
                    modulo="data_fusion",
                    mensagem=(
                        f"Confiabilidade {resultado.confiabilidade:.2%} ({resultado.nivel})"
                        + (", evento promovido para ativo" if promovido else "")
                        + (", evento rebaixado para em análise" if rebaixado else "")
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
            )
        db.commit()
        db.refresh(evento)
        if mudou_status:
            _publicar_evento_atualizado(db, evento.id)

    return resultado, evento


def _publicar_evento_atualizado(db: Session, evento_id: int) -> None:
    """Importa aqui dentro para evitar import circular com detection_events."""
    try:
        from app.services.detection_events import publicar_evento

        publicar_evento(db, evento_id)
    except Exception:
        pass


def promover_eventos_por_confiabilidade(db: Session) -> int:
    """Recalcula os eventos abertos e ajusta o status de cada um.

    Promove os que passaram do limite de confiabilidade e devolve para análise
    os que caíram abaixo dele.
    """
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
