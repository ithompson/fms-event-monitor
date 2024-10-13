import argparse
import asyncio

from fmsmonitor.field_monitor import FieldMonitor

async def run(args):
    queue = asyncio.Queue
    field_monitor = FieldMonitor(queue, args.fms_address)

    await field_monitor.run()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fms_address', type=str, default='10.0.100.5')

    args = parser.parse_args()

    asyncio.run(run(args))