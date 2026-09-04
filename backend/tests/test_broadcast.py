"""Testes de broadcast sync→async e cleanup SSE."""

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.broadcast import schedule_coroutine, set_main_loop
from app.routers import tempo_real


@pytest.mark.asyncio
async def test_schedule_coroutine_runs_on_main_loop() -> None:
    loop = asyncio.get_running_loop()
    set_main_loop(loop)
    done = asyncio.Event()

    async def task() -> None:
        done.set()

    schedule_coroutine(task())
    await asyncio.wait_for(done.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_schedule_coroutine_from_worker_thread() -> None:
    loop = asyncio.get_running_loop()
    set_main_loop(loop)
    done = asyncio.Event()

    async def task() -> None:
        done.set()

    thread = threading.Thread(target=schedule_coroutine, args=(task(),))
    thread.start()
    thread.join(timeout=1.0)
    await asyncio.wait_for(done.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_event_stream_cleanup_removes_client() -> None:
    tempo_real._clients.clear()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    tempo_real._clients.append(queue)

    gen = tempo_real._event_stream(queue)
    await queue.put("event: teste\\n\\n")
    await anext(gen)
    await gen.aclose()

    assert queue not in tempo_real._clients


def test_evento_detectado_envia_sse(client: TestClient, db_session, criar_evento) -> None:
    """O SSE é alimentado pela detecção (``publicar_evento``), não por rota."""
    from app.services import detection_events

    evento = criar_evento(titulo="SSE Broadcast", tipo="alagamento", severidade="alta")

    tempo_real._clients.clear()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    tempo_real._clients.append(queue)
    try:
        detection_events.publicar_evento(db_session, evento.id, tipo_mensagem="evento_criado")

        deadline = time.monotonic() + 2.0
        while queue.empty() and time.monotonic() < deadline:
            time.sleep(0.01)

        body = queue.get_nowait()
        assert "evento_criado" in body
        assert "SSE Broadcast" in body
    finally:
        tempo_real._clients.clear()
