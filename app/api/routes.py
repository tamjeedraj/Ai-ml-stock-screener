import asyncio

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect
)


router = APIRouter()

clients = set()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket.accept()

    clients.add(websocket)

    try:

        while True:
            await asyncio.sleep(30)

    except WebSocketDisconnect:

        clients.discard(websocket)

    except Exception:

        clients.discard(websocket)


async def broadcast(data):

    dead = []

    for client in list(clients):

        try:

            await client.send_json(data)

        except Exception:

            dead.append(client)

    for client in dead:

        clients.discard(client)