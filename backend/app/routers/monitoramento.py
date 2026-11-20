"""Situação do monitoramento das câmeras.

Mostra a configuração e o resumo da última passada de cada ritmo: a completa,
feita quando o sistema liga, o ciclo geral das câmeras com evento e a
verificação das câmeras sem evento.
"""

from fastapi import APIRouter

from app.config import settings
from app.services import ciclo_monitoramento

router = APIRouter(prefix="/monitoramento", tags=["monitoramento"])


@router.get("/status")
def status_monitoramento() -> dict:
    return {
        "ativo": settings.gx_monitoramento_ativo,
        "ciclo_minutos": settings.gx_ciclo_minutos,
        "sem_evento_segundos": settings.gx_ciclo_sem_evento_segundos,
        "ciclos_sem_confirmacao_para_remover": settings.gx_ciclos_sem_confirmacao_para_remover,
        "cameras": len(ciclo_monitoramento.cameras_monitoradas()),
        "ultimas_passadas": ciclo_monitoramento.ultimos_resumos(),
    }
