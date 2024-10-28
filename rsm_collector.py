#!/usr/bin/env python3
"""Collector for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import functools
import machineid

from websockets.asyncio.server import broadcast, serve

from rsm_collector import async_setup_entry
from rsm_collector.coordinator import SensorData
from rsm_collector.hass_stubs import DEFAULT_SCAN_INTERVAL, ConfigEntry, HomeAssistant

from myjsonrpc import JsonRpc, JsonRpcNotification
from myjsonrpc.transports.websocket_transport import WebsocketsServerTransport

CONNECTIONS = set()

API_VERSION = "0.0.2"

async def myjsonrpc_handler(websocket, machine_id: str, newest_data: SensorData):
    async def _on_get_api_info() -> dict:
        logging.info("Get api info")
        return {
            "version": API_VERSION,
            "id": "RemoteSystemMonitorCollectorApi",
        }

    async def _on_get_machine_info() -> dict:
        logging.info("Get machine info")
        return {
            "id": machine_id,
            "os": platform.system(),
            "os_alias": platform.system_alias(
                platform.system(), platform.release(), platform.version()
            ),
            "version": platform.version(),
            "release": platform.release(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    async def _on_get_initial_data() -> dict:
        logging.info("Get initial data")
        return {"data": newest_data.as_dict()}

    disconnected_future: asyncio.Future = asyncio.Future()

    async def _on_disconnect() -> None:
        disconnected_future.set_result(None)

    transport = WebsocketsServerTransport(websocket, on_disconnect=_on_disconnect)

    jsonrpc = JsonRpc(transport)
    jsonrpc.register_request_handler("get_api_info", _on_get_api_info)
    jsonrpc.register_request_handler("get_machine_info", _on_get_machine_info)
    jsonrpc.register_request_handler("get_initial_data", _on_get_initial_data)

    await transport.connect()

    await disconnected_future


async def websocket_handler(websocket, machine_id: str, newest_data: SensorData):
    CONNECTIONS.add(websocket)

    try:
        logging.info("New connection from %s", websocket.remote_address)
        await myjsonrpc_handler(websocket, machine_id, newest_data)
        logging.info("Connection closed from %s", websocket.remote_address)
    finally:
        CONNECTIONS.remove(websocket)


async def main(args):
    print("Remote System Monitor Collector")
    print(f"API version: {API_VERSION}")
    print("------------------------------")

    hass = HomeAssistant()
    entry = ConfigEntry()

    await async_setup_entry(hass, entry)

    assert entry.runtime_data is not None

    # Subscribe all disks for updates
    disk_arguments = entry.runtime_data.coordinator._arguments
    for disk_argument in disk_arguments:
        entry.runtime_data.coordinator.update_subscribers[("disks", disk_argument)] = (
            "dummy"  # Would normally be entity_id
        )

    # Subscribe all / most data for updates
    entry.runtime_data.coordinator.update_subscribers[("swap", "")] = set("dummy")
    entry.runtime_data.coordinator.update_subscribers[("memory", "")] = set("dummy")
    entry.runtime_data.coordinator.update_subscribers[("io_counters", "")] = set("dummy")
    # entry.runtime_data.coordinator.update_subscribers[("addresses", "")] = set("dummy")
    entry.runtime_data.coordinator.update_subscribers[("load", "")] = set("dummy")
    entry.runtime_data.coordinator.update_subscribers[("cpu_percent", "")] = set("dummy")
    ## Technically not needed to send all the time since when rebooting collector will be restarted anyway
    ## But lets leave it in for now to avoid additional work now
    entry.runtime_data.coordinator.update_subscribers[("boot", "")] = set("dummy")
    ## I don't have a case for monitoring processes and it seems like a lot of data. Leave out for now
    # # entry.runtime_data.coordinator.update_subscribers[("processes", "")] = set("dummy")
    # entry.runtime_data.coordinator.update_subscribers[("temperatures", "")] = set("dummy")

    new_data: SensorData = await entry.runtime_data.coordinator._async_update_data()

    machine_id = (
        args.machine_id
        if args.machine_id is not None
        else machineid.hashed_id("RemoteSystemMonitorCollector")
    )  # Don't change the app id because it would change the machine id !!!

    # This binds the websocket_handler function with the machine_id and new_data arguments pre-filled.
    # This is needed because the serve function requires a function with only one argument (websocket) but
    # our websocket_handler has three arguments.
    bound_websocket_handler = functools.partial(
        websocket_handler, machine_id=machine_id, newest_data=new_data
    )

    async with serve(bound_websocket_handler, "0.0.0.0", 2604):
        while True:
            new_data = await entry.runtime_data.coordinator._async_update_data()

            notification = JsonRpcNotification(
                "update_data", {"data": new_data.as_dict()}
            )

            # print(json.dumps(json.loads(str(notification)), indent=2))
            broadcast(CONNECTIONS, str(notification))

            await asyncio.sleep(DEFAULT_SCAN_INTERVAL)


if __name__ == "__main__":
    ## Commandlineoptions
    parser = argparse.ArgumentParser(description="Remote SystemMonitor collector.")
    parser.add_argument(
        "--machine-id",
        type=str,
        help="Machine ID to use. Only intended to be used when the actual machine ID changed for some unexpected reason.",
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
