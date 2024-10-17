#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

import websockets.asyncio
from websockets.asyncio.client import ClientConnection
import websockets


DEFAULT_PORT = 2604

class RemoteSystemMonitorApi:
    def __init__(self, host: str, port: int = DEFAULT_PORT, on_new_data=None) -> None:
        self.host = host
        self.port = port
        self._on_new_data = on_new_data
        self._receive_task: asyncio.Task | None = None


    async def connect(self):
        uri = f"ws://{self.host}:{self.port}"
        self._connection: ClientConnection = await websockets.asyncio.client.connect(uri)
        self._receive_task = asyncio.create_task(self._receiver())


    async def disconnect(self):
        if self._connection:
            await self._connection.close()

    async def _receiver(self) -> None:
        while True:
            try:
                message = await self._connection.recv()
                logging.debug(f"_receiver -- {message}")

                try:
                    jsonrpc_message = json.loads(message)
                    if jsonrpc_message.get("jsonrpc",None) != "2.0":
                        raise Exception("Invalid/unsupported JSON-RPC data")
                    if jsonrpc_message["method"] != "update_data":
                        raise Exception("Unsupported JSON-RPC method")
                    
                    await self._on_new_data(jsonrpc_message["params"]["data"])
                except json.JSONDecodeError:
                    logging.warning(f"Invalid message: {message}")
                    pass

            except websockets.ConnectionClosed:
                logging.info("Connection closed")
                break


async def main(args):

    async def on_new_data(data):
        print(f"### THE DATA ### -- {data}")

    api = RemoteSystemMonitorApi(args.host, args.port, on_new_data=on_new_data)
    await api.connect()

    while True:
        await asyncio.sleep(5)
        print(".")


if __name__ == "__main__":

    ## Commandlineoptions
    parser = argparse.ArgumentParser(description="Remote SystemMonitor client API.")
    parser.add_argument(
        "host",
        type=str,
        help="The hostname or IP of the server to connect to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=2604,
        help="The port to connect to. Default is 2604.",
    )
    parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Define loglevel, default is INFO.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    asyncio.run(main(args))
