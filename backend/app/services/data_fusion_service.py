import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.evento import Evento

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_fusion.fusion import calcular_confiabilidade  # noqa: E402
from data_fusion.models import EventoFusionInput, FonteInfo, ResultadoFusao  # noqa: E402

# Mapeamento heurístico do campo texto `fonte` para o motor de fusão
_TIPOS_FONTE = {
    "api": "api",
    "prefeitura": "api",
    "sensor": "sensor",
    "yolo": "yolo",
    "ia": "yolo",
    "manual": "manual",
    "data_fusion": "data_fusion",
    "fusion": "data_fusion",
}


def _inferir_tipo_fonte(fonte: str | None) -> str:
    if not fonte:
        return "manual"
    fonte_lower = fonte.lower()
    for chave, tipo in _TIPOS_FONTE.items():
        if chave in fonte_lower:
            return tipo
    return "manual"


def evento_para_fusao(evento: Evento) -> EventoFusionInput:
    fonte = FonteInfo(
        tipo=_inferir_tipo_fonte(evento.fonte),
        nome=evento.fonte or "desconhecida",
        ativo=True,
    )
    return EventoFusionInput(
        evento_id=evento.id,
        tipo=evento.tipo,
        evidencias_ia=[],
        dados_clima=[],
        fonte=fonte,
    )


def aplicar_fusao_evento(
    db: Session,
    evento_id: int,
    *,
    persistir: bool = False,
) -> tuple[ResultadoFusao, Evento]:
    evento = db.get(Evento, evento_id)
    if not evento:
        raise ValueError(f"Evento {evento_id} não encontrado")

    resultado = calcular_confiabilidade(evento_para_fusao(evento))

    if persistir:
        evento.confiabilidade = float(resultado.confiabilidade)
        db.commit()
        db.refresh(evento)

    return resultado, evento
