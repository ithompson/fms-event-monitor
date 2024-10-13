import enum
import logging
import json
from websockets.asyncio.server import serve, ServerConnection

from typing import Callable, Dict, List, Set

logger = logging.getLogger(__name__)

class Notifier(enum.Enum):
    MatchLifecycle = "matchLifecycle"
    MatchLoad = "matchLoad"
    MatchTime = "matchTime"
    MatchTiming = "matchTiming"

ENDPOINTS: Dict[str, List[Notifier]] = {
    "/api/match_lifecycle/websocket": [Notifier.MatchLifecycle],
    "/displays/field_monitor/websocket": [Notifier.MatchTiming, Notifier.MatchLoad, Notifier.MatchTime],
    "/api/arena/websocket": [Notifier.MatchTiming, Notifier.MatchLoad, Notifier.MatchTime],
}

class CheesyWebsocketServer:
    def __init__(self, port: int, data_callback: Callable[[Notifier], any]):
        self._port = port
        self._data_callback = data_callback

        self._listeners: Dict[Notifier, Set[ServerConnection]] = {}
        for notifier in Notifier:
            self._listeners[notifier] = set()

    async def run(self):
        # Run a websocket server that listens on the specified port indefinitely
        server = await serve(self._handle_connection, None, self._port)
        await server.serve_forever()

    async def _handle_connection(self, websocket: ServerConnection):
        # Register the websocket for the appropriate notifiers
        path = websocket.request.path.split('?')[0].rstrip("/")
        notifiers_for_connection = ENDPOINTS.get(path, [])
        logger.info(f"New websocket connection for {path}, subscribing to {notifiers_for_connection}")
        for notifier in notifiers_for_connection:
            # Send the initial data for this notifier
            await self._broadcast_notification(notifier, {websocket})
            # Register for future updates
            self._listeners[notifier].add(websocket)

        try:
            async for message in websocket:
                # Discard all inbound messages
                pass
        finally:
            # Unregister all listeners for this websocket
            for notifier in notifiers_for_connection:
                self._listeners[notifier].discard(websocket)

    async def _broadcast_notification(self, notifier: Notifier, targets: Set[ServerConnection]):
        logger.debug(f"Broadcasting {notifier} to {len(targets)} targets")
        data = self._data_callback(notifier)
        encoded_msg = json.dumps({
            "type": notifier.value,
            "data": data,
        })
        for websocket in targets:
            await websocket.send(encoded_msg)

    async def notify(self, notifier: Notifier):
        await self._broadcast_notification(notifier, self._listeners[notifier])