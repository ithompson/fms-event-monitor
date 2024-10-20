import enum
import json
import logging
from collections.abc import Callable

from websockets.asyncio.server import ServerConnection, serve

logger = logging.getLogger(__name__)


class ServerNotYetRunningError(Exception):
    def __init__(self):
        super().__init__("Server not yet running")


class Notifier(enum.Enum):
    MatchLifecycle = "matchLifecycle"
    MatchLoad = "matchLoad"
    MatchTime = "matchTime"
    MatchTiming = "matchTiming"


ENDPOINTS: dict[str, list[Notifier]] = {
    "/api/match_lifecycle/websocket": [Notifier.MatchLifecycle],
    "/displays/field_monitor/websocket": [
        Notifier.MatchTiming,
        Notifier.MatchLoad,
        Notifier.MatchTime,
    ],
    "/api/arena/websocket": [
        Notifier.MatchTiming,
        Notifier.MatchLoad,
        Notifier.MatchTime,
    ],
}


class CheesyWebsocketServer:
    def __init__(self, port: int, data_callback: Callable[[Notifier], any]):
        self._port = port
        self._data_callback = data_callback
        self._server = None

        self._listeners: dict[Notifier, set[ServerConnection]] = {}
        for notifier in Notifier:
            self._listeners[notifier] = set()

    async def open_server_socket(self):
        self._server = await serve(self._handle_connection, None, self._port)

    async def run(self):
        # Run a websocket server that listens on the specified port indefinitely
        if not self._server:
            await self.open_server_socket()
        await self._server.serve_forever()

    def get_listen_socket(self):
        if not self._server:
            raise ServerNotYetRunningError
        return self._server.sockets[0]

    async def _handle_connection(self, websocket: ServerConnection):
        # Register the websocket for the appropriate notifiers
        path = websocket.request.path.split("?")[0].rstrip("/")
        notifiers_for_connection = ENDPOINTS.get(path, [])
        logger.info("New websocket connection for %s, subscribing to %s", path, notifiers_for_connection)
        for notifier in notifiers_for_connection:
            # Send the initial data for this notifier
            await self._broadcast_notification(notifier, {websocket})
            # Register for future updates
            self._listeners[notifier].add(websocket)

        try:
            async for _ in websocket:
                # Discard all inbound messages
                pass
        finally:
            # Unregister all listeners for this websocket
            for notifier in notifiers_for_connection:
                self._listeners[notifier].discard(websocket)

    async def _broadcast_notification(self, notifier: Notifier, targets: set[ServerConnection]):
        logger.debug("Broadcasting %s to %d clients", notifier.name, len(targets))
        data = self._data_callback(notifier)
        encoded_msg = json.dumps(
            {
                "type": notifier.value,
                "data": data,
            }
        )
        for websocket in targets:
            await websocket.send(encoded_msg)

    async def notify(self, notifier: Notifier):
        await self._broadcast_notification(notifier, self._listeners[notifier])
