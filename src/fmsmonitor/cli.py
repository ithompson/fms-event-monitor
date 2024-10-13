import argparse
import asyncio
import logging

from .field_monitor import FieldMonitor
from .event_publisher import EventPublisher

logger = logging.getLogger(__name__)

async def run(args):
    fms_event_queue = asyncio.Queue()
    field_monitor = FieldMonitor(fms_event_queue, args.fms_address)
    event_publisher = EventPublisher(fms_event_queue, args.websocket_port)

    await asyncio.gather(
        field_monitor.run(),
        event_publisher.run(),
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fms_address', type=str, default='10.0.100.5')
    parser.add_argument('--websocket_port', type=int, default=5805)
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)

    loop = asyncio.get_event_loop()
    main_task = loop.create_task(run(args))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        main_task.cancel()
        try:
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
        loop.close()