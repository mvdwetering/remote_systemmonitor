#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import logging

from mashumaro.mixins.dict import DataClassDictMixin

# Some hackery to be able to use the "internal" package
try:
    from .jsonrpc import JsonRpcAioHttpWebsocketClientTransport, JsonRpc
except ImportError:
    from jsonrpc import JsonRpcAioHttpWebsocketClientTransport, JsonRpc


DEFAULT_PORT = 2604

@dataclass
class ApiInfo(DataClassDictMixin):
    version:str
    id:str

@dataclass
class MachineInfo(DataClassDictMixin):
    hostname:str
    os:str
    os_alias:str
    version:str
    release:str
    platform:str
    machine:str
    processor:str


class RemoteSystemMonitorApi:
    def __init__(self, host: str, port: int = DEFAULT_PORT, on_new_data=None) -> None:
        self.host = host
        self.port = port
        self._on_new_data = on_new_data
        # TODO: remove this
        self._last_data = None

        # TODO: Need to do something with disconnects/connection errors, probably on backend??
        self._backend = JsonRpcAioHttpWebsocketClientTransport()
        self._jsonrpc = JsonRpc(self._backend)
        self._jsonrpc.register_notification_handler("update_data", self._on_update_data_notification)

    async def connect(self):
        uri = f"ws://{self.host}:{self.port}"
        await self._backend.connect(uri)
        logging.debug("Connected")


    async def disconnect(self):
        logging.debug("Disconnect")
        await self._backend.disconnect()

    async def _on_update_data_notification(self, data) -> None:
        self._last_data = data
        if self._on_new_data is not None: 
            await self._on_new_data(data)


    async def get_api_info(self) -> ApiInfo:
        response = await self._jsonrpc.call_method("get_api_info")

        if response.error is not None:
            raise Exception(f"Error: {response.error}")

        api_info = ApiInfo.from_dict(response.result)
        if api_info.id != "RemoteSystemMonitorApi":
            raise Exception("Not a RemoteSystemMonitorApi")

        return api_info

    async def get_machine_info(self) -> MachineInfo:
        response = await self._jsonrpc.call_method("get_machine_info")

        if response.error is not None:
            raise Exception(f"Error: {response.error}")
        return MachineInfo.from_dict(response.result)


async def main(args):

    data_received = 0

    async def on_new_data(data):
        nonlocal data_received
        print(f"### THE DATA ### -- {data}")
        data_received = data_received + 1

    api = RemoteSystemMonitorApi(args.host, args.port, on_new_data=on_new_data)
    await api.connect()

    api_info = await api.get_api_info()
    print(api_info)
    if api_info.version != "0.0.1":
        raise Exception("Unsupported API version")

    machine_info = await api.get_machine_info()
    print(machine_info)

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
