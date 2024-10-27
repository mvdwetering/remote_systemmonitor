#!/usr/bin/env python3
"""Collector API for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any

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


class NamedTupleStringDecoder:

    @classmethod
    def from_tuple_string(cls, named_tuple_string: str):
        matches = re.findall(r"(\w+)\s*=\s*(\d+(?:\.\d+)?)", named_tuple_string)
        return cls(**dict(matches))

@dataclass(frozen=True, kw_only=True)
class DiskUsage(NamedTupleStringDecoder):
    total: int
    used: int
    free: int
    percent: float

    def __post_init__(self):
        object.__setattr__(self, "total", int(self.total))
        object.__setattr__(self, "used", int(self.used))
        object.__setattr__(self, "free", int(self.free))
        object.__setattr__(self, "percent", float(self.percent))

@dataclass(frozen=True, kw_only=True)
class Memory(NamedTupleStringDecoder):
    total: int
    available: int
    percent: float
    used: int
    free: int

    def __post_init__(self):
        object.__setattr__(self, "total", int(self.total))
        object.__setattr__(self, "available", int(self.available))
        object.__setattr__(self, "percent", float(self.percent))
        object.__setattr__(self, "used", int(self.used))
        object.__setattr__(self, "free", int(self.free))

@dataclass(frozen=True, kw_only=True, slots=True)
class SensorData:
    """Sensor data."""

    disk_usage: dict[str, Any]
    # swap: sswap
    memory: Memory
    # io_counters: dict[str, snetio]
    # addresses: dict[str, list[snicaddr]]
    # load: tuple[float, float, float]
    cpu_percent: float | None
    # boot_time: datetime
    # processes: list[Process]
    # temperatures: dict[str, list[shwtemp]]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SensorData:
        # disk_usage = {k: str(v) for k, v in self.disk_usage.items()}
        return SensorData(
            disk_usage={k: DiskUsage.from_tuple_string(v) for k, v in data["disk_usage"].items()},
            # swap=data.get("swap"),
            memory=Memory.from_tuple_string(data["memory"]),
            # io_counters=data.get("io_counters"),
            # addresses=data.get("addresses"),
            # load=data.get("load"),
            cpu_percent=float(data["cpu_percent"]),
            # boot_time=data.get("boot_time"),
            # processes=data.get("processes"),
            # temperatures=data.get("temperatures"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        disk_usage = None
        if self.disk_usage:
            disk_usage = {k: str(v) for k, v in self.disk_usage.items()}
        # io_counters = None
        # if self.io_counters:
        #     io_counters = {k: str(v) for k, v in self.io_counters.items()}
        # addresses = None
        # if self.addresses:
        #     addresses = {k: str(v) for k, v in self.addresses.items()}
        # temperatures = None
        # if self.temperatures:
        #     temperatures = {k: str(v) for k, v in self.temperatures.items()}
        return {
            "disk_usage": disk_usage,
            # "swap": str(self.swap),
            "memory": str(self.memory),
            # "io_counters": io_counters,
            # "addresses": addresses,
            # "load": str(self.load),
            # "cpu_percent": str(self.cpu_percent),
            # "boot_time": str(self.boot_time),
            # "processes": str(self.processes),
            # "temperatures": temperatures,
        }


class RemoteSystemMonitorCollectorApi:
    def __init__(self, host: str, port: int = DEFAULT_PORT, on_new_data=None) -> None:
        self.host = host
        self.port = port
        self._on_new_data = on_new_data
        self._last_data: SensorData | None = None

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
        sensor_data = SensorData.from_dict(data)

        self._last_data = sensor_data
        if self._on_new_data is not None: 
            await self._on_new_data(sensor_data)


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

            self._last_data = SensorData.from_dict(response.result['data'])

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
