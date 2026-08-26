"""Router de Server-Sent Events para atualizações em tempo real."""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["tempo-real"])

# Filas de clientes conectados
_clients: list[asyncio.Queue[str]] = []
_lock = asyncio.Lock()


async def _broadcast(event_type: str, data: dict) -> None:
    """Envia evento para todos os clientes SSE conectados."""
    payload = f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
    async with _lock:
        dead: list[asyncio.Queue[str]] = []
        for q in _clients:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _clients.remove(q)


async def _event_stream(queue: asyncio.Queue[str]) -> AsyncGenerator[str, None]:
    """Generator que yields eventos SSE de uma fila."""
    try:
        # Heartbeat a cada 15s para manter conexão viva
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield data
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        async with _lock:
            if queue in _clients:
                _clients.remove(queue)


@router.get("/events/stream")
async def stream_events(request: Request) -> StreamingResponse:
    """Endpoint SSE — cliente recebe eventos em tempo real.

    Eventos enviados:
    - evento_criado: quando um novo evento é registrado
    - evento_atualizado: quando evento é modificado (PATCH)
    - evento_removido: quando evento é deletado
    """
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    async with _lock:
        _clients.append(queue)

    return StreamingResponse(
        _event_stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events/connected")
async def connected_clients() -> dict[str, int]:
    """Retorna número de clientes SSE conectados."""
    return {"connected": len(_clients)}
