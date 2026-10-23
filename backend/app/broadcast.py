"""Agenda tarefas assíncronas no loop principal a partir de outras threads."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def schedule_coroutine(coro: Coroutine[Any, Any, Any]) -> None:
    """Manda a tarefa para o loop principal. Pode ser chamada de qualquer thread."""
    if _main_loop is None or not _main_loop.is_running():
        # Sem loop rodando (testes e scripts), fecha a tarefa para não gerar aviso.
        coro.close()
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, _main_loop)
    except Exception:
        coro.close()
        logger.exception("Falha ao agendar coroutine")
