#!/usr/bin/env python3
"""Collector for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform

from websockets.asyncio.server import broadcast, serve

from rsm_collector import async_setup_entry
from rsm_collector.hass_stubs import DEFAULT_SCAN_INTERVAL, ConfigEntry, HomeAssistant

from myjsonrpc import JsonRpcWebsocketsTransport, JsonRpc, JsonRpcNotification

CONNECTIONS = set()


async def myjsonrpc_handler(websocket):
    async def _on_get_api_info() -> dict:
        return {
            "version": "0.0.1",
            "id": "RemoteSystemMonitorCollectorApi",
        }

    async def _on_get_machine_info() -> dict:
        return {
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

    disconnected_future: asyncio.Future = asyncio.Future()

    async def _on_disconnect() -> None:
        disconnected_future.set_result(None)

    backend = JsonRpcWebsocketsTransport(websocket, on_disconnect=_on_disconnect)

    jsonrpc = JsonRpc(backend)
    jsonrpc.register_request_handler("get_api_info", _on_get_api_info)
    jsonrpc.register_request_handler("get_machine_info", _on_get_machine_info)

    await backend.connect()

    await disconnected_future


async def websocket_handler(websocket):
    CONNECTIONS.add(websocket)

    try:
        logging.info("New connection from %s", websocket.remote_address)
        await myjsonrpc_handler(websocket)
        logging.info("Connection closed from %s", websocket.remote_address)
    finally:
        CONNECTIONS.remove(websocket)


async def main(args):
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
    entry.runtime_data.coordinator.update_subscribers[("swap", "")] = "dummy"
    entry.runtime_data.coordinator.update_subscribers[("memory", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("io_counters", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("addresses", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("load", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("cpu_percent", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("boot", "")] = "dummy"
    # # entry.runtime_data.coordinator.update_subscribers[("processes", "")] = "dummy"
    # entry.runtime_data.coordinator.update_subscribers[("temperatures", "")] = "dummy"

    async with serve(websocket_handler, "0.0.0.0", 2604):
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
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Define loglevel, default is INFO.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    asyncio.run(main(args))
