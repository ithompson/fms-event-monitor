import asyncio
from dataclasses import dataclass
import enum
import logging
from playwright.async_api import async_playwright
import re

logger = logging.getLogger(__name__)

class MatchState(enum.Enum):
    UNKNOWN = enum.auto()
    WAITING_FOR_PRESTART = enum.auto()
    NOT_READY = enum.auto()
    READY = enum.auto()
    RUNNING_AUTO = enum.auto()
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
    match_state: MatchState
    match_number: int

MONITOR_STATE_TABLE = {
    "READY TO PRE-START": MatchState.WAITING_FOR_PRESTART,
    "PRE-START INITIATED": MatchState.WAITING_FOR_PRESTART,
    "PRE-START COMPLETED": MatchState.NOT_READY,
    "MATCH NOT READY": MatchState.NOT_READY,
    "MATCH READY": MatchState.READY,
    "CLEARING GAME DATA": MatchState.RUNNING_AUTO,
    "MATCH RUNNING (AUTO)": MatchState.RUNNING_AUTO,
    "MATCH TRANSITIONING": MatchState.RUNNING_AUTO,
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
    def __init__(self, event_queue: asyncio.Queue, fms_address: str):
        self._event_queue = event_queue
        self._fms_address = fms_address
        self._current_state = MatchState.UNKNOWN
        self._current_match_number = 0

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            page.on("console", self._console_callback)

            await page.expose_function("__scriptEvent", self._script_event_callback)
            await page.add_init_script(FIELD_MONITOR_SCRIPT)

            await page.goto(f"http://{self._fms_address}/FieldMonitor")

            # Block until this task is cancelled. Playwright is
            # internally running tasks to dispatch callbacks from
            # our browser-side script, and we need to keep the
            # Playwright context alive to receive these events.
            dummy_future = asyncio.get_event_loop().create_future()
            await dummy_future

    async def _script_event_callback(self, event):
        try:
            logger.debug(f"Received event from field monitor: {event}")
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
                        if self._current_state == MatchState.FINISHED and match_state == MatchState.WAITING_FOR_PRESTART:
                            match_state = MatchState.SCORES_POSTED

                        self._current_state = match_state
                        await self._send_lifecycle_update()
                case "match_number":
                    if m := re.match(r"M: (\d+)", field_value):
                        self._current_match_number = int(m.group(1))
                        await self._send_lifecycle_update()
                case _:
                    pass
        except Exception as e:
            logger.exception("Error processing field monitor event", exc_info=e)

    async def _send_lifecycle_update(self):
        event_to_send = MatchLifecycleState(self._current_state, self._current_match_number)
        logger.info(f"Sending lifecycle update: {event_to_send}")
        await self._event_queue.put(event_to_send)

    async def _console_callback(self, message):
        logger.info(f"Field monitor JS console message: {message}")