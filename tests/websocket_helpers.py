import json
import socket
from contextlib import asynccontextmanager

from websockets.asyncio.client import connect


@asynccontextmanager
async def ws_client(server, endpoint="/api/match_lifecycle/websocket"):
    """Create a websocket client that connects to the specified server"""
    sock = server.get_listen_socket()
    listen_port = sock.getsockname()[1]
    if sock.family == socket.AF_INET:
        address = f"127.0.0.1:{listen_port}"
    else:
        address = f"[::1]:{listen_port}"
    async with connect(f"ws://{address}{endpoint}") as ws:
        yield ws


def ws_message(type, data):
    """Encode a websocket message into the expected JSON string"""
    return json.dumps({"type": type, "data": data})


async def assert_msg(ws, type, data):
    """Wait for a websocket message and check that it matches the expected message"""
    message = await ws.recv()
    assert message == ws_message(type, data)
