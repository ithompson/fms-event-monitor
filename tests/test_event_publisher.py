import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fmsmonitor.cheesy_websocket import Notifier
from fmsmonitor.event_publisher import EventPublisher
from fmsmonitor.field_monitor import MatchLifecycleState, MatchState, UpdateType

from .websocket_helpers import *


async def test_event_publisher(mocker):
    cons = mocker.patch(
        "fmsmonitor.event_publisher.CheesyWebsocketServer", autospec=True
    )
    event_queue = asyncio.Queue()
    publisher = EventPublisher(event_queue, 12345)
    cons.assert_called_once_with(12345, publisher._websocket_data_callback)

    publisher_task = asyncio.create_task(publisher.run())

    try:
        await asyncio.sleep(0)
        publisher._cheesy_socket.run.assert_called_once()

        # Check the initial data
        assert publisher._websocket_data_callback(Notifier.MatchLifecycle) == {
            "UpdateType": UpdateType.MATCH_STATE.name,
            "MatchState": MatchState.UNKNOWN.name,
            "MatchNumber": 0,
            "Timestamp": "0001-01-01T00:00:00",
        }

        # Check that MATCH_STATE updates dispatch to the websocket
        event_timestamp = datetime.now()
        event_queue.put_nowait(
            MatchLifecycleState(
                UpdateType.MATCH_STATE, MatchState.READY, 1, event_timestamp
            )
        )
        await asyncio.sleep(0)
        publisher._cheesy_socket.notify.assert_has_calls(
            [mocker.call(Notifier.MatchLifecycle), mocker.call(Notifier.MatchTime)]
        )
        publisher._cheesy_socket.notify.reset_mock()
        assert event_queue.empty()
        # Check that the state was updated
        assert publisher._websocket_data_callback(Notifier.MatchLifecycle) == {
            "UpdateType": UpdateType.MATCH_STATE.name,
            "MatchState": MatchState.READY.name,
            "MatchNumber": 1,
            "Timestamp": event_timestamp.isoformat(),
        }

        # Check a MATCH_NUMBER update
        event_queue.put_nowait(
            MatchLifecycleState(
                UpdateType.MATCH_NUMBER, MatchState.READY, 2, event_timestamp
            )
        )
        await asyncio.sleep(0)
        publisher._cheesy_socket.notify.assert_has_calls(
            [mocker.call(Notifier.MatchLifecycle), mocker.call(Notifier.MatchLoad)]
        )
        publisher._cheesy_socket.notify.reset_mock()
        assert event_queue.empty()
        # Check that the state was updated
        assert publisher._websocket_data_callback(Notifier.MatchLifecycle) == {
            "UpdateType": UpdateType.MATCH_NUMBER.name,
            "MatchState": MatchState.READY.name,
            "MatchNumber": 2,
            "Timestamp": event_timestamp.isoformat(),
        }

    finally:
        publisher_task.cancel()
        try:
            await publisher_task
        except asyncio.CancelledError:
            pass


@asynccontextmanager
async def ws_publisher(queue):
    publisher = EventPublisher(queue, 0)
    server_task = asyncio.create_task(publisher.run())
    try:
        yield publisher
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


async def assert_lifecycle_msg(ws, event):
    encoded_msg = {
        "UpdateType": event.update_type.name,
        "MatchState": event.match_state.name,
        "MatchNumber": event.match_number,
        "Timestamp": event.timestamp.isoformat(),
    }
    await assert_msg(ws, "matchLifecycle", encoded_msg)


async def test_publisher_websocket():
    # End-to-end test of the EventPublisher with a websocket client
    event_queue = asyncio.Queue()
    async with ws_publisher(event_queue) as publisher:
        # Give the publisher time to spawn the websocket server
        await asyncio.sleep(0.1)

        # Check that the server sends an initial state to clients that connect before the first event
        async with ws_client(publisher._cheesy_socket) as ws:
            await assert_lifecycle_msg(ws, MatchLifecycleState.default())

        # Push a state update
        ready_msg = MatchLifecycleState(
            UpdateType.MATCH_STATE, MatchState.READY, 1, datetime.now()
        )
        event_queue.put_nowait(ready_msg)

        async with ws_client(publisher._cheesy_socket) as ws:
            # Check that the server sends the current state when a client connects after the first event
            await assert_lifecycle_msg(ws, ready_msg)

            # Check that the server pushes events to clients
            event_sequence = [
                MatchLifecycleState(
                    UpdateType.MATCH_STATE, MatchState.NOT_READY, 1, datetime.now()
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_STATE, MatchState.READY, 1, datetime.now()
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_STATE, MatchState.RUNNING_AUTO, 1, datetime.now()
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_STATE, MatchState.ABORTED, 1, datetime.now()
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_STATE,
                    MatchState.WAITING_FOR_PRESTART,
                    1,
                    datetime.now(),
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_NUMBER,
                    MatchState.WAITING_FOR_PRESTART,
                    2,
                    datetime.now(),
                ),
                MatchLifecycleState(
                    UpdateType.MATCH_STATE, MatchState.NOT_READY, 2, datetime.now()
                ),
            ]

            # Submit all of the events to the publisher
            for event in event_sequence:
                event_queue.put_nowait(event)

            # Verify that the client receives all of the messages in order
            for event in event_sequence:
                await assert_lifecycle_msg(ws, event)
