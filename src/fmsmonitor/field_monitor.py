import asyncio
import datetime as dt
import enum
import logging
import re
from dataclasses import dataclass

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class MatchState(enum.Enum):
    UNKNOWN = enum.auto()
    WAITING_FOR_PRESTART = enum.auto()
    NOT_READY = enum.auto()
    READY = enum.auto()
    STARTING_MATCH = enum.auto()
    RUNNING_AUTO = enum.auto()
    RUNNING_PERIOD_TRANSITION = enum.auto()
    RUNNING_TELEOP = enum.auto()
    FINISHED = enum.auto()
    SCORES_POSTED = enum.auto()
    ABORTED = enum.auto()

    @classmethod
    def from_monitor_state(cls, monitor_state: str):
        return MONITOR_STATE_TABLE.get(monitor_state, cls.UNKNOWN)


class UpdateType(enum.Enum):
    MATCH_STATE = enum.auto()
    MATCH_NUMBER = enum.auto()


@dataclass
class MatchLifecycleState:
    update_type: UpdateType
    match_state: MatchState
    match_number: int
    timestamp: dt.datetime

    @staticmethod
    def default():
        return MatchLifecycleState(UpdateType.MATCH_STATE, MatchState.UNKNOWN, 0, dt.datetime.min)


MONITOR_STATE_TABLE = {
    "READY TO PRE-START": MatchState.WAITING_FOR_PRESTART,
    "PRE-START INITIATED": MatchState.WAITING_FOR_PRESTART,
    "PRE-START COMPLETED": MatchState.NOT_READY,
    "MATCH NOT READY": MatchState.NOT_READY,
    "MATCH READY": MatchState.READY,
    "CLEARING GAME DATA": MatchState.STARTING_MATCH,
    "MATCH RUNNING (AUTO)": MatchState.RUNNING_AUTO,
    "MATCH TRANSITIONING": MatchState.RUNNING_PERIOD_TRANSITION,
    "MATCH RUNNING (TELEOP)": MatchState.RUNNING_TELEOP,
    "MATCH OVER": MatchState.FINISHED,
    "READY FOR POST-RESULT": MatchState.FINISHED,
    "MATCH ABORTED": MatchState.ABORTED,
}

FIELD_MONITOR_SCRIPT = """
console.log('Field monitor script loaded');

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM loaded");

    function installTextStateObserver(name, node) {
        let current_text = "";
        let observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.addedNodes.length === 1) {
                    let new_text = mutation.addedNodes[0].textContent;
                    if (new_text !== current_text) {
                        current_text = new_text;
                        window.__scriptEvent({field: name, value: new_text});
                    }
                }
            });
        });
        observer.observe(node, { childList: true });
        console.log(`Observer installed for ${name}`);
    }

    installTextStateObserver("match_state", document.querySelector("#matchStateTop"));
    installTextStateObserver("match_number", document.querySelector("#MatchNumber"));
});
"""


class FieldMonitor:
    def __init__(self, event_queue: asyncio.Queue, url: str):
        self._event_queue = event_queue
        self._current_state = MatchState.UNKNOWN
        self._current_match_number = 0
        self._field_monitor_url = url
        self._close_future = None

    async def run(self):
        logger.debug("Launching field monitor browser")
        self._close_future = asyncio.get_event_loop().create_future()
        async with async_playwright() as p:
            self._browser = await p.chromium.launch()
            self._page = await self._browser.new_page()
            self._page.on("console", self._console_callback)

            await self._page.expose_function("__scriptEvent", self._script_event_callback)
            await self._page.add_init_script(FIELD_MONITOR_SCRIPT)

            await self._page.goto(self._field_monitor_url)

            # Block until we're asked to close. Playwright is
            # internally running tasks to dispatch callbacks from
            # our browser-side script, and we need to keep the
            # Playwright context alive to receive these events.
            await self._close_future

    async def close(self):
        if self._close_future is None:
            return
        await self._browser.close()
        self._close_future.set_result(None)

    async def _script_event_callback(self, event):
        try:
            logger.debug("Received event from field monitor: %s", event)
            field_name = event["field"]
            field_value = event["value"]
            match field_name:
                case "match_state":
                    match_state = MatchState.from_monitor_state(field_value)
                    # Need to deduplicate match state updates here because multiple FMS states map to a single MatchState
                    if match_state != self._current_state:
                        # Special case: A FINISHED -> WAITING_FOR_PRESTART transition indicates that scores were posted.
                        # Record a SCORES_POSTED state instead. This is a bit of a hack, but it's the best we can do since
                        # the field monitor doesn't distinguish the reason for a WAITING_FOR_PRESTART state.
                        if (
                            self._current_state == MatchState.FINISHED
                            and match_state == MatchState.WAITING_FOR_PRESTART
                        ):
                            match_state = MatchState.SCORES_POSTED

                        self._current_state = match_state
                        await self._send_lifecycle_update(UpdateType.MATCH_STATE)
                case "match_number":
                    if m := re.match(r"M: (\d+)", field_value):
                        self._current_match_number = int(m.group(1))
                        await self._send_lifecycle_update(UpdateType.MATCH_NUMBER)
                case _:
                    pass
        except Exception as e:
            logger.exception("Error processing field monitor event", exc_info=e)

    async def _send_lifecycle_update(self, update_type: UpdateType):
        event_to_send = MatchLifecycleState(
            update_type,
            self._current_state,
            self._current_match_number,
            dt.datetime.now(dt.timezone.utc),
        )
        logger.info("Sending lifecycle update: %s", event_to_send)
        await self._event_queue.put(event_to_send)

    async def _console_callback(self, message):
        logger.info("Field monitor JS console message: %s", message)
