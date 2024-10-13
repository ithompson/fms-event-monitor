#!/usr/bin/env python3

import argparse
import json
from websockets.sync.client import connect

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=5805)
    parser.add_argument('--endpoint', type=str, default='/api/match_lifecycle/websocket')

    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}{args.endpoint}"
    with connect(uri) as websocket:
        while True:
            message = json.loads(websocket.recv())
            print(message)

if __name__ == '__main__':
    main()