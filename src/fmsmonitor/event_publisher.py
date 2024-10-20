import asyncio

from fmsmonitor.cheesy_websocket import CheesyWebsocketServer, Notifier
from fmsmonitor.field_monitor import MatchLifecycleState, MatchState, UpdateType

CHEESY_STATE_ENCODINGS: dict[MatchState, int] = {
    MatchState.UNKNOWN: 0,  # PRE_MATCH
    MatchState.WAITING_FOR_PRESTART: 0,  # PRE_MATCH
    MatchState.NOT_READY: 0,  # PRE_MATCH
    MatchState.READY: 0,  # PRE_MATCH
    MatchState.STARTING_MATCH: 1,  # START_MATCH
    MatchState.RUNNING_AUTO: 3,  # AUTO_PERIOD
    MatchState.RUNNING_PERIOD_TRANSITION: 4,  # PAUSE_PERIOD
    MatchState.RUNNING_TELEOP: 5,  # TELEOP_PERIOD
    MatchState.FINISHED: 6,  # POST_MATCH
    MatchState.SCORES_POSTED: 6,  # POST_MATCH
    MatchState.ABORTED: 6,  # POST_MATCH
}


class EventPublisher:
    def __init__(self, fms_event_queue: asyncio.Queue, port: int):
        self._fms_event_queue = fms_event_queue
        self._current_fms_state: MatchLifecycleState = MatchLifecycleState.default()
        self.cheesy_socket = CheesyWebsocketServer(port, self._websocket_data_callback)

    async def run(self):
        await asyncio.gather(
            self.cheesy_socket.run(),
            self._pump_fms_events(),
        )

    async def _pump_fms_events(self):
        while True:
            self._current_fms_state = await self._fms_event_queue.get()
            match self._current_fms_state.update_type:
                case UpdateType.MATCH_STATE:
                    await self.cheesy_socket.notify(Notifier.MatchLifecycle)
                    await self.cheesy_socket.notify(Notifier.MatchTime)
                case UpdateType.MATCH_NUMBER:
                    await self.cheesy_socket.notify(Notifier.MatchLifecycle)
                    await self.cheesy_socket.notify(Notifier.MatchLoad)
            self._fms_event_queue.task_done()

    def _websocket_data_callback(self, notifier: Notifier):
        match notifier:
            case Notifier.MatchLifecycle:
                return {
                    "UpdateType": self._current_fms_state.update_type.name,
                    "MatchState": self._current_fms_state.match_state.name,
                    "MatchNumber": self._current_fms_state.match_number,
                    "Timestamp": self._current_fms_state.timestamp.isoformat(),
                }
            case Notifier.MatchLoad:
                return {
                    "Match": {
                        "LongName": f"M {self._current_fms_state.match_number}",
                        "ShortName": f"M {self._current_fms_state.match_number}",
                        "Status": CHEESY_STATE_ENCODINGS.get(self._current_fms_state.match_state, 0),
                        # Future improvement: Read the team numbers from the field monitor and populate them here
                        "Red1": 0,
                        "Red1IsSurrogate": False,
                        "Red2": 0,
                        "Red2IsSurrogate": False,
                        "Red3": 0,
                        "Red3IsSurrogate": False,
                        "Blue1": 0,
                        "Blue1IsSurrogate": False,
                        "Blue2": 0,
                        "Blue2IsSurrogate": False,
                        "Blue3": 0,
                        "Blue3IsSurrogate": False,
                    },
                    "AllowSubstitution": False,
                    "IsReplay": False,
                    "Teams": {},
                    "Rankings": {},
                    "Matchup": None,
                    "RedOffFieldTeams": [],
                    "BlueOffFieldTeams": [],
                    "BreakDescription": "",
                }
            case Notifier.MatchTime:
                return {
                    "MatchState": CHEESY_STATE_ENCODINGS.get(self._current_fms_state.match_state, 0),
                    "MatchTimeSec": 0,
                }
            case Notifier.MatchTiming:
                return {
                    "AutoDurationSec": 15,
                    "PauseDurationSec": 3,
                    "TeleopDurationSec": 135,
                    "TimeoutDurationSec": 0,
                    "WarmupDurationSec": 0,
                    "WarningRemainingDurationSec": 20,
                }
            case _:
                msg = f"Unknown notifier: {notifier}"
                raise ValueError(msg)
