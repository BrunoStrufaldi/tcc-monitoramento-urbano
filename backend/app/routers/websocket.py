"""WebSocket que avisa o painel em tempo real.

O servidor manda uma mensagem quando um evento é criado, atualizado ou
removido. Se o painel mandar "ping", o servidor responde "pong".
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws_manager import WSMessage, manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Abre o canal assim que o painel se conecta."""
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

