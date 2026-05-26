from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config.config import WEBSOCKET

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text(f"connected to {WEBSOCKET['url']}")
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"echo: {message}")
    except WebSocketDisconnect:
        return
