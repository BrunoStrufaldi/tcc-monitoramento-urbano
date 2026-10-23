"""Testes do tempo real do painel: WebSocket, SSE e envio entre threads."""

import asyncio
import json
import threading
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.broadcast import schedule_coroutine, set_main_loop
from app.routers import tempo_real
from app.ws_manager import ConnectionManager, WSMessage


class MockWebSocket:
    """WebSocket falso para testar o ConnectionManager."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.accepted = False
        self._closed = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self._closed:
            raise ConnectionError("closed")
        self.messages.append(data)

    def close(self) -> None:
        self._closed = True


async def _noop() -> None:
    return None


@pytest.mark.asyncio
async def test_manager_envia_para_todos_no_formato_do_protocolo() -> None:
    manager = ConnectionManager()
    assert manager.count == 0
    assert await manager.broadcast(WSMessage("teste", {})) == 0

    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)
    assert ws1.accepted and manager.count == 2

    enviados = await manager.broadcast_evento("evento_criado", {"id": 1, "titulo": "Teste", "extra": {"a": True}})
    assert enviados == 2
    payload = json.loads(ws2.messages[0])
    assert set(payload) == {"tipo", "timestamp", "dados"}
    assert payload["tipo"] == "evento_criado"
    assert payload["dados"] == {"id": 1, "titulo": "Teste", "extra": {"a": True}}
    datetime.fromisoformat(payload["timestamp"])

    manager.disconnect(ws1)
    manager.disconnect(ws1)  # desconectar duas vezes não pode falhar
    assert manager.count == 1


@pytest.mark.asyncio
async def test_manager_remove_conexoes_que_cairam() -> None:
    manager = ConnectionManager()
    viva, morta = MockWebSocket(), MockWebSocket()
    await manager.connect(viva)
    await manager.connect(morta)
    morta.close()

    assert await manager.broadcast(WSMessage("teste", {})) == 1
    assert manager.count == 1


def test_websocket_responde_ping_com_pong(client: TestClient) -> None:
    """O canal em tempo real aceita uma sessão real e responde ao heartbeat."""
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["tipo"] == "pronto"
        websocket.send_json({"tipo": "ping"})
        message = websocket.receive_json()
    assert message["tipo"] == "pong"
    assert set(message) == {"tipo", "timestamp", "dados"}


def test_publicar_evento_transmite_atualizacao(db_session, criar_evento, monkeypatch) -> None:
    """publicar_evento é o que manda o evento_atualizado depois de recalcular a fusão."""
    from app.services import detection_events

    enviados: list[tuple[str, dict]] = []
    monkeypatch.setattr(detection_events, "schedule_coroutine", lambda coro: coro.close())
    monkeypatch.setattr(
        detection_events.ws_manager, "broadcast_evento",
        lambda tipo, dados: enviados.append((tipo, dados)) or _noop(),
    )

    evento = criar_evento(titulo="Original", tipo="transito")
    detection_events.publicar_evento(db_session, evento.id)

    assert enviados and enviados[0][0] == "evento_atualizado"
    assert enviados[0][1]["titulo"] == "Original"


def test_evento_detectado_chega_pelo_sse(client: TestClient, db_session, criar_evento) -> None:
    """O SSE recebe os eventos da detecção, não de uma rota."""
    from app.services import detection_events

    evento = criar_evento(titulo="SSE Broadcast", tipo="alagamento", severidade="alta")

    tempo_real._clients.clear()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    tempo_real._clients.append(queue)
    try:
        assert client.get("/events/connected").json()["connected"] == 1

        detection_events.publicar_evento(db_session, evento.id, tipo_mensagem="evento_criado")

        deadline = time.monotonic() + 2.0
        while queue.empty() and time.monotonic() < deadline:
            time.sleep(0.01)

        body = queue.get_nowait()
        assert "evento_criado" in body
        assert "SSE Broadcast" in body
    finally:
        tempo_real._clients.clear()


@pytest.mark.asyncio
async def test_sse_remove_cliente_quando_fecha() -> None:
    tempo_real._clients.clear()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    tempo_real._clients.append(queue)

    gen = tempo_real._event_stream(queue)
    await queue.put("event: teste\\n\\n")
    await anext(gen)
    await gen.aclose()

    assert queue not in tempo_real._clients


@pytest.mark.asyncio
async def test_schedule_coroutine_entrega_no_loop_principal() -> None:
    """As threads das câmeras mandam mensagens para o loop do servidor."""
    set_main_loop(asyncio.get_running_loop())
    done = asyncio.Event()

    async def task() -> None:
        done.set()

    thread = threading.Thread(target=schedule_coroutine, args=(task(),))
    thread.start()
    thread.join(timeout=1.0)
    await asyncio.wait_for(done.wait(), timeout=1.0)

    # Sem loop a coroutine é fechada, para não virar "never awaited".
    set_main_loop(None)
    coro = task()
    schedule_coroutine(coro)
    assert coro.cr_frame is None
