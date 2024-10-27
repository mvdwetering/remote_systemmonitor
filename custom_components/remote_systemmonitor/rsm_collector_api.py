#!/usr/bin/env python3
"""Collector API for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import logging

from mashumaro.mixins.dict import DataClassDictMixin

# Some hackery to be able to use the "internal" package
try:
    from .myjsonrpc import JsonRpc
    from .myjsonrpc.transports.aiohttp_websocketclient_transport import AioHttpWebsocketClientTransport
except ImportError:
    from myjsonrpc import JsonRpc
    from myjsonrpc.transports.aiohttp_websocketclient_transport import AioHttpWebsocketClientTransport


DEFAULT_PORT = 2604

@dataclass
class ApiInfo(DataClassDictMixin):
    version:str
    id:str

@dataclass
class MachineInfo(DataClassDictMixin):
    id: str
    hostname:str
    os:str
    os_alias:str
    version:str
    release:str
    platform:str
    machine:str
    processor:str


class RemoteSystemMonitorCollectorApi:
    def __init__(self, host: str, port: int = DEFAULT_PORT, on_new_data=None) -> None:
        self.host = host
        self.port = port
        self._on_new_data = on_new_data
        # TODO: remove this
        self._last_data = None

        # TODO: Need to do something with disconnects/connection errors, probably on transport??
        self._transport = AioHttpWebsocketClientTransport()
        self._jsonrpc = JsonRpc(self._transport)
        self._jsonrpc.register_notification_handler("update_data", self._on_update_data_notification)

    async def connect(self):
        uri = f"ws://{self.host}:{self.port}"
        await self._transport.connect(uri)
        logging.debug("Connected")


    async def disconnect(self):
        logging.debug("Disconnect")
        await self._transport.disconnect()

    async def _on_update_data_notification(self, data) -> None:
        self._last_data = data
        if self._on_new_data is not None: 
            await self._on_new_data(data)


    async def get_api_info(self) -> ApiInfo:
        response = await self._jsonrpc.call_method("get_api_info")

        if response.error is not None:
            raise Exception(f"Error: {response.error}")

        api_info = ApiInfo.from_dict(response.result)
        if api_info.id != "RemoteSystemMonitorCollectorApi":
            raise Exception("Not a RemoteSystemMonitorCollectorApi")

        return api_info

    async def get_machine_info(self) -> MachineInfo:
        response = await self._jsonrpc.call_method("get_machine_info")

        if response.error is not None:
            raise Exception(f"Error: {response.error}")
        return MachineInfo.from_dict(response.result)

    async def get_initial_data(self):
        if self._last_data is None:
            response = await self._jsonrpc.call_method("get_initial_data")
            if response.error is not None:
                raise Exception(f"Error: {response.error}")

            self._last_data = response.result['data']

        return self._last_data




async def main(args):

    data_received = 0

    async def on_new_data(data):
        nonlocal data_received
        print(f"### NEW DATA ### -- {data}")
        data_received = data_received + 1

    api = RemoteSystemMonitorCollectorApi(args.host, args.port, on_new_data=on_new_data)
    await api.connect()

    api_info = await api.get_api_info()
    print(api_info)
    if api_info.version != "0.0.2":
        raise Exception(f"Unsupported API version: {api_info.version}")

    machine_info = await api.get_machine_info()
    print(machine_info)

    initial_data = await api.get_initial_data()
    print(initial_data)

    done = False
    while not done:
        await asyncio.sleep(5)
        print(".")
        if data_received > 2:
            print("\n** ENOUGH DATA WAS RECEIVED **")
            done = True

    await api.disconnect()


if __name__ == "__main__":

    ## Commandlineoptions
    parser = argparse.ArgumentParser(description="Remote SystemMonitor client API.")
    parser.add_argument(
        "host",
        type=str,
        help="The hostname or IP of the collector to connect to.",
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
