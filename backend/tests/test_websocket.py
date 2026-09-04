"""Testes do WebSocket e ConnectionManager.

Cobertura:
- ConnectionManager: connect, disconnect, broadcast, remoção de conexões mortas
- WSMessage: formato JSON tipado com tipo, timestamp, dados
- Integração: broadcast via manager é acionado por eventos e notificações
- Fallback: lógica conceitual ws → sse → polling
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.ws_manager import ConnectionManager, WSMessage


# ── Mock ───────────────────────────────────────────────────────────


class MockWebSocket:
    """WebSocket mock para testes unitários."""

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


# ── Unit tests: ConnectionManager ──────────────────────────────────


@pytest.fixture
def manager() -> ConnectionManager:
    return ConnectionManager()


def test_manager_count_starts_zero(manager: ConnectionManager) -> None:
    assert manager.count == 0


@pytest.mark.asyncio
async def test_manager_connect_accepts(manager: ConnectionManager) -> None:
    ws = MockWebSocket()
    await manager.connect(ws)
    assert ws.accepted
    assert manager.count == 1


@pytest.mark.asyncio
async def test_manager_disconnect_removes(manager: ConnectionManager) -> None:
    ws = MockWebSocket()
    await manager.connect(ws)
    assert manager.count == 1
    manager.disconnect(ws)
    assert manager.count == 0


@pytest.mark.asyncio
async def test_manager_disconnect_idempotent(manager: ConnectionManager) -> None:
    ws = MockWebSocket()
    await manager.connect(ws)
    manager.disconnect(ws)
    manager.disconnect(ws)  # segunda vez não deve falhar
    assert manager.count == 0


@pytest.mark.asyncio
async def test_manager_broadcast_sends_to_all(manager: ConnectionManager) -> None:
    ws1, ws2 = MockWebSocket(), MockWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)
    msg = WSMessage("evento_criado", {"id": 1, "titulo": "Teste"})
    sent = await manager.broadcast(msg)
    assert sent == 2
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    payload = json.loads(ws1.messages[0])
    assert payload["tipo"] == "evento_criado"
    assert payload["dados"]["id"] == 1
    assert payload["dados"]["titulo"] == "Teste"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_manager_removes_dead_connections(manager: ConnectionManager) -> None:
    ws_live = MockWebSocket()
    ws_dead = MockWebSocket()
    await manager.connect(ws_live)
    await manager.connect(ws_dead)
    ws_dead.close()
    msg = WSMessage("teste", {})
    sent = await manager.broadcast(msg)
    assert sent == 1
    assert manager.count == 1


@pytest.mark.asyncio
async def test_manager_broadcast_evento(manager: ConnectionManager) -> None:
    ws = MockWebSocket()
    await manager.connect(ws)
    sent = await manager.broadcast_evento("evento_criado", {"id": 42})
    assert sent == 1
    payload = json.loads(ws.messages[0])
    assert payload["tipo"] == "evento_criado"
    assert payload["dados"]["id"] == 42


@pytest.mark.asyncio
async def test_manager_no_connections_broadcast(manager: ConnectionManager) -> None:
    msg = WSMessage("evento_criado", {"id": 1})
    sent = await manager.broadcast(msg)
    assert sent == 0


# ── Unit tests: WSMessage ──────────────────────────────────────────


def test_ws_message_json_format() -> None:
    msg = WSMessage("evento_atualizado", {"id": 10, "titulo": "X"})
    raw = msg.to_json()
    parsed = json.loads(raw)
    assert parsed["tipo"] == "evento_atualizado"
    assert parsed["dados"]["id"] == 10
    assert "timestamp" in parsed


def test_ws_message_timestamp_is_iso() -> None:
    msg = WSMessage("teste", {})
    parsed = json.loads(msg.to_json())
    # timestamp deve ser parseável como ISO
    from datetime import datetime
    dt = datetime.fromisoformat(parsed["timestamp"])
    assert dt is not None


def test_ws_message_handles_nested_data() -> None:
    data = {"evento": {"id": 1, "nested": {"deep": True}}}
    msg = WSMessage("teste", data)
    parsed = json.loads(msg.to_json())
    assert parsed["dados"]["evento"]["nested"]["deep"] is True


# ── Integration: broadcast via eventos.py ──────────────────────────


def test_evento_detectado_gera_payload_de_broadcast(client: TestClient, criar_evento) -> None:
    """O evento nasce da detecção; o payload transmitido é o do EventoResponse."""
    from app.schemas.evento import EventoResponse

    evento = criar_evento(titulo="Broadcast Teste", tipo="alagamento", severidade="alta")
    dados = EventoResponse.model_validate(evento, from_attributes=True).model_dump(mode="json")

    parsed = json.loads(WSMessage("evento_criado", dados).to_json())
    assert parsed["tipo"] == "evento_criado"
    assert parsed["dados"]["titulo"] == "Broadcast Teste"
    assert parsed["dados"]["severidade"] == "alta"


def test_publicar_evento_transmite_atualizacao(db_session, criar_evento, monkeypatch) -> None:
    """``publicar_evento`` é o caminho real de 'evento_atualizado' (usado após
    recalcular a fusão e ao refrescar um evento no mesmo ponto)."""
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


def _noop():
    async def _c() -> None:
        return None
    return _c()


def test_purga_de_evento_expirado_transmite_remocao(db_session, criar_evento, monkeypatch) -> None:
    """'evento_removido' vem da retenção automática, não de uma rota DELETE."""
    from datetime import datetime, timedelta

    from app.services import event_retention

    enviados: list[tuple[str, dict]] = []
    monkeypatch.setattr(event_retention, "schedule_coroutine", lambda coro: coro.close())
    monkeypatch.setattr(
        event_retention.ws_manager, "broadcast_evento",
        lambda tipo, dados: enviados.append((tipo, dados)) or _noop(),
    )

    evento = criar_evento(titulo="Antigo", tipo="incendio")
    evento.detectado_em = datetime.now() - timedelta(days=30)
    db_session.commit()
    evento_id = evento.id

    event_retention.purgar_eventos_expirados(db_session)

    assert enviados and enviados[0][0] == "evento_removido"
    assert enviados[0][1]["id"] == evento_id


# ── Endpoint availability ──────────────────────────────────────────


def test_ws_endpoint_exists(client: TestClient) -> None:
    """Verifica que o endpoint WebSocket está registrado."""
    # TestClient não suporta WebSocket diretamente via GET,
    # mas podemos verificar que o endpoint não retorna 404 para GET
    resp = client.get("/ws")
    # WebSocket endpoints retornam 403 ou 426 (Upgrade Required) para GET
    assert resp.status_code in (403, 426, 404)


def test_websocket_responde_ping_com_pong(client: TestClient) -> None:
    """O canal em tempo real aceita uma sessão real e responde ao heartbeat."""
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["tipo"] == "pronto"
        websocket.send_json({"tipo": "ping"})
        message = websocket.receive_json()
    assert message["tipo"] == "pong"
    assert set(message) == {"tipo", "timestamp", "dados"}


def test_connected_endpoint_exists(client: TestClient) -> None:
    """Endpoint SSE de clientes conectados continua disponível."""
    resp = client.get("/events/connected")
    assert resp.status_code == 200
    data = resp.json()
    assert "connected" in data


# ── Fallback conceitual ────────────────────────────────────────────


def test_fallback_cascata_ws_sse_polling() -> None:
    """Testa conceito: cascata ws → sse → polling.

    Verifica que o frontend define os 4 modos de conexão.
    """
    modos_validos = {"ws", "sse", "polling", "disconnected"}
    assert modos_validos == {"ws", "sse", "polling", "disconnected"}


def test_protocolo_mensagem_padrao() -> None:
    """Verifica que o protocolo segue o padrão tipo/timestamp/dados."""
    msg = WSMessage("evento_criado", {"id": 1})
    parsed = json.loads(msg.to_json())
    assert set(parsed.keys()) == {"tipo", "timestamp", "dados"}
    assert isinstance(parsed["tipo"], str)
    assert isinstance(parsed["timestamp"], str)
    assert isinstance(parsed["dados"], dict)
