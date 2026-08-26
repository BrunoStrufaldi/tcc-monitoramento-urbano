"""Agenda coroutines no event loop principal a partir de endpoints sync (thread pool)."""

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
    """Envia coroutine para o loop principal — seguro a partir de threads sync."""
    if _main_loop is None or not _main_loop.is_running():
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, _main_loop)
    except Exception:
        logger.exception("Falha ao agendar coroutine")
