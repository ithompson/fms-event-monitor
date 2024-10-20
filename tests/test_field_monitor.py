import asyncio
from pathlib import Path

import pytest
from fmsmonitor.field_monitor import *


def test_match_lifecycle_state():
    state = MatchLifecycleState(
        UpdateType.MATCH_STATE, MatchState.READY, 1, datetime.now()
    )
    assert state.update_type == UpdateType.MATCH_STATE
    assert state.match_state == MatchState.READY
    assert state.match_number == 1


def test_match_lifecycle_state_default():
    state = MatchLifecycleState.default()
    assert state.update_type == UpdateType.MATCH_STATE
    assert state.match_state == MatchState.UNKNOWN
    assert state.match_number == 0
    assert state.timestamp == datetime.min


@pytest.mark.timeout(10)
async def test_event_detection():
    test_page_path = Path(__file__).resolve().parent / "static/field_monitor_test.html"
    test_page_uri = f"file://{test_page_path}"

    event_queue = asyncio.Queue()
    monitor = FieldMonitor(event_queue, test_page_uri)

    monitor_task = asyncio.create_task(monitor.run())

    # The expected updates from the unit test javascript
    expected_updates = [
        # Initial state as data first loads
        (UpdateType.MATCH_NUMBER, MatchState.UNKNOWN, 1),
        # One full match cycle with scores posted
        (UpdateType.MATCH_STATE, MatchState.WAITING_FOR_PRESTART, 1),
        (UpdateType.MATCH_STATE, MatchState.NOT_READY, 1),
        (UpdateType.MATCH_STATE, MatchState.READY, 1),
        (UpdateType.MATCH_STATE, MatchState.STARTING_MATCH, 1),
        (UpdateType.MATCH_STATE, MatchState.RUNNING_AUTO, 1),
        (UpdateType.MATCH_STATE, MatchState.RUNNING_PERIOD_TRANSITION, 1),
        (UpdateType.MATCH_STATE, MatchState.RUNNING_TELEOP, 1),
        (UpdateType.MATCH_STATE, MatchState.FINISHED, 1),
        (UpdateType.MATCH_STATE, MatchState.SCORES_POSTED, 1),
        (UpdateType.MATCH_STATE, MatchState.WAITING_FOR_PRESTART, 1),
        (UpdateType.MATCH_NUMBER, MatchState.WAITING_FOR_PRESTART, 2),
        (UpdateType.MATCH_STATE, MatchState.NOT_READY, 2),
        # One additional match cycle that aborts during auto
        (UpdateType.MATCH_STATE, MatchState.READY, 2),
        (UpdateType.MATCH_STATE, MatchState.STARTING_MATCH, 2),
        (UpdateType.MATCH_STATE, MatchState.RUNNING_AUTO, 2),
        (UpdateType.MATCH_STATE, MatchState.ABORTED, 2),
        (UpdateType.MATCH_STATE, MatchState.WAITING_FOR_PRESTART, 2),
    ]

    try:
        for update in expected_updates:
            event = await event_queue.get()
            assert (event.update_type, event.match_state, event.match_number) == update
            event_queue.task_done()
    finally:
        await monitor._browser.close()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
