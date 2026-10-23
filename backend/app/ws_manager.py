"""Controla as conexões WebSocket abertas com o painel."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSMessage:
    """Mensagem tipada para o protocolo WebSocket."""

    def __init__(self, tipo: str, dados: dict[str, Any]) -> None:
        self.tipo = tipo
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.dados = dados

    def to_json(self) -> str:
        return json.dumps(
            {"tipo": self.tipo, "timestamp": self.timestamp, "dados": self.dados},
            default=str,
        )


class ConnectionManager:
    """Guarda as conexões WebSocket abertas e envia mensagens para todas."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Aceita e registra uma nova conexão WebSocket."""
        await websocket.accept()
        await self.register(websocket)

    async def register(self, websocket: WebSocket) -> None:
        """Registra uma conexão que já foi aceita."""
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WS conectado, total: %d", self.count)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove uma conexão WebSocket."""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info("WS desconectado, total: %d", self.count)

    async def broadcast(self, message: WSMessage) -> int:
        """Envia a mensagem para todos os clientes e devolve quantos receberam."""
        payload = message.to_json()
        sent = 0
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                    sent += 1
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)
        if dead:
            logger.info("Removidas %d conexões mortas", len(dead))
        return sent

    async def broadcast_evento(self, event_type: str, data: dict[str, Any]) -> int:
        """Atalho para enviar um evento, no mesmo formato usado no SSE."""
        return await self.broadcast(WSMessage(event_type, data))


# Instância global compartilhada entre routers
manager = ConnectionManager()
