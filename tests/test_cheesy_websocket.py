import asyncio
from contextlib import asynccontextmanager

import pytest
from fmsmonitor.cheesy_websocket import *

from .websocket_helpers import *

# Ensure all websocket tests time out if a message is missed
pytestmark = [pytest.mark.timeout(5)]


@asynccontextmanager
async def ws_server(notifier):
    server = CheesyWebsocketServer(0, notifier)
    await server.open_server_socket()
    server_task = asyncio.create_task(server.run())
    try:
        yield server
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.fixture
async def simple_server():
    async with ws_server(lambda _: {}) as server:
        yield server


async def test_basic_connection(simple_server):
    # Test that a client can connect to the server
    async with ws_client(simple_server, endpoint="/"):
        pass


async def test_initial_push(simple_server):
    # Test that the server sends a message to a client when it connects
    async with ws_client(simple_server) as ws:
        message = await ws.recv()
        assert message == ws_message("matchLifecycle", {})


async def test_notify(simple_server):
    # Test that the server sends a notification to a client when a notifier is triggered
    async with ws_client(simple_server) as ws:
        await assert_msg(ws, "matchLifecycle", {})
        await simple_server.notify(Notifier.MatchLifecycle)
        await assert_msg(ws, "matchLifecycle", {})

        for _ in range(4):
            await simple_server.notify(Notifier.MatchLifecycle)
        for _ in range(4):
            await assert_msg(ws, "matchLifecycle", {})


@pytest.mark.parametrize(
    "endpoint", ["/api/arena/websocket", "/displays/field_monitor/websocket"]
)
async def test_multiple_notifiers(simple_server, endpoint):
    # Test that the server can interleave messages from multiple notifiers
    async with ws_client(simple_server, endpoint=endpoint) as ws:
        # Initial messages
        await assert_msg(ws, "matchTiming", {})
        await assert_msg(ws, "matchLoad", {})
        await assert_msg(ws, "matchTime", {})
        # Send a batch of notifications
        await simple_server.notify(Notifier.MatchLifecycle)
        await simple_server.notify(Notifier.MatchTime)
        await simple_server.notify(Notifier.MatchTime)
        await simple_server.notify(Notifier.MatchLoad)
        await simple_server.notify(Notifier.MatchTime)
        await assert_msg(ws, "matchTime", {})
        await assert_msg(ws, "matchTime", {})
        await assert_msg(ws, "matchLoad", {})
        await assert_msg(ws, "matchTime", {})


async def test_notifier_data():
    # Test that the server sends the correct data when a notifier is triggered
    notifier_data = {"foo": "bar"}

    def notifier(_):
        return notifier_data

    async with ws_server(notifier) as server:
        async with ws_client(server) as ws:
            await assert_msg(ws, "matchLifecycle", notifier_data)
            await server.notify(Notifier.MatchLifecycle)
            await assert_msg(ws, "matchLifecycle", notifier_data)

            msg_1 = {"stuff": 6, "things": "abcd"}
            msg_2 = {"fdsafasd": 27, "ffff": "qqqq"}

            notifier_data = msg_1
            await server.notify(Notifier.MatchLifecycle)
            notifier_data = msg_2
            await server.notify(Notifier.MatchLifecycle)

            await assert_msg(ws, "matchLifecycle", msg_1)
            await assert_msg(ws, "matchLifecycle", msg_2)
