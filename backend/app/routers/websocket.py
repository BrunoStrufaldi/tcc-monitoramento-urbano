"""Router WebSocket para atualizações em tempo real.

Protocolo:
  Servidor → Cliente:
    {"tipo": "evento_criado",    "timestamp": "...", "dados": {...}}
    {"tipo": "evento_atualizado","timestamp": "...", "dados": {...}}
    {"tipo": "evento_removido",  "timestamp": "...", "dados": {...}}

  Cliente → Servidor:
    {"tipo": "ping"}  → responde {"tipo": "pong"}

Sem autenticação: o canal é aberto assim que a conexão é aceita e o servidor
anuncia {"tipo": "pronto"} — o cliente não precisa enviar nada antes.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws_manager import WSMessage, manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Canal operacional: aberto na conexão, sem handshake prévio."""
    await websocket.accept()
    try:
        await manager.register(websocket)
        await websocket.send_json({"tipo": "pronto"})
        while True:
            try:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                    if msg.get("tipo") == "ping":
                        await websocket.send_text(
                            WSMessage("pong", {}).to_json()
                        )
                except json.JSONDecodeError:
                    pass
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WS erro de conexão")
        try:
            await websocket.close(code=1008)
        except RuntimeError:
            pass
    finally:
        manager.disconnect(websocket)

