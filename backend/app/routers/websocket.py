"""Router WebSocket para atualizações em tempo real.

Protocolo:
  Servidor → Cliente:
    {"tipo": "evento_criado",    "timestamp": "...", "dados": {...}}
    {"tipo": "evento_atualizado","timestamp": "...", "dados": {...}}
    {"tipo": "evento_removido",  "timestamp": "...", "dados": {...}}
    {"tipo": "notificacao_criada","timestamp": "...","dados": {...}}
    {"tipo": "notificacao_atualizada","timestamp": "...","dados": {...}}

  Cliente → Servidor:
    {"tipo": "ping"}  → responde {"tipo": "pong"}
"""

import json
import logging
import base64
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws_manager import WSMessage, manager
from app.config import settings
from app.security import decode_access_token
from app.services.visual_validation import visual_validation_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Canal operacional autenticado por mensagem inicial ``auth``."""
    await websocket.accept()
    try:
        initial = json.loads(await websocket.receive_text())
        token = str(initial.get("token", "")) if initial.get("tipo") == "auth" else ""
        if token:
            # Sistema sem login: só validamos quando um token é enviado.
            try:
                decode_access_token(token)
            except Exception:
                await websocket.send_json({"tipo": "erro", "detalhe": "Token inválido"})
                await websocket.close(code=1008)
                return
        await manager.register(websocket)
        await websocket.send_json({"tipo": "auth_ok"})
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


@router.websocket("/ws/cv")
async def websocket_cv(websocket: WebSocket) -> None:
    """Canal de frames: exige mensagem inicial auth e nunca persiste imagens."""
    await websocket.accept()
    last_frame_at = 0.0
    try:
        while True:
            message = json.loads(await websocket.receive_text())
            if message.get("tipo") == "auth":
                token = str(message.get("token", ""))
                if token:
                    try:
                        decode_access_token(token)
                    except Exception:
                        await websocket.send_json({"tipo": "erro", "detalhe": "Token inválido"})
                        await websocket.close(code=1008)
                        return
                await websocket.send_json({"tipo": "auth_ok", "max_fps": settings.yolo_max_fps})
                continue
            if message.get("tipo") != "frame":
                await websocket.send_json({"tipo": "erro", "detalhe": "Mensagem não suportada"})
                continue
            now = time.monotonic()
            if now - last_frame_at < 1 / settings.yolo_max_fps:
                await websocket.send_json({"tipo": "frame_ignorado", "motivo": "limite_fps"})
                continue
            last_frame_at = now
            try:
                content = base64.b64decode(message.get("conteudo", ""), validate=True)
                result = visual_validation_service.validate_frame(content, str(message.get("mime", "")), str(message.get("frame_id", "")), message.get("threshold"))
                await websocket.send_json({"tipo": "frame_resultado", "dados": {**result.__dict__, "deteccoes": [item.__dict__ for item in result.deteccoes]}})
            except (ValueError, RuntimeError) as exc:
                await websocket.send_json({"tipo": "erro", "detalhe": str(exc)})
    except WebSocketDisconnect:
        return
    except Exception:
        logger.debug("WS CV encerrado", exc_info=True)
