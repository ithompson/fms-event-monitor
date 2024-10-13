import argparse
import asyncio
import logging

from fmsmonitor.field_monitor import FieldMonitor

logger = logging.getLogger(__name__)

async def run(args):
    queue = asyncio.Queue()
    field_monitor = FieldMonitor(queue, args.fms_address)

    await field_monitor.run()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fms_address', type=str, default='10.0.100.5')
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level)

    asyncio.run(run(args), debug=True)