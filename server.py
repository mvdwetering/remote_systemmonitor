#!/usr/bin/env python3
"""Server for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform

from websockets.asyncio.server import broadcast, serve

from server import async_setup_entry
from server.hass_stubs import DEFAULT_SCAN_INTERVAL, ConfigEntry, HomeAssistant

CONNECTIONS = set()

async def consumer_handler(websocket):
    async for message in websocket:
        print(message)
        try:
            json_data = json.loads(message)
            if json_data["method"] == "get_api_info":
                response = {
                    "jsonrpc": "2.0",
                    "id": json_data["id"],
                    "result": {
                        "version": "0.0.1",
                        "id": "RemoteSystemMonitorApi",
                    }
                }
                await websocket.send(json.dumps(response))
                continue

            if json_data["method"] == "get_machine_info":
                response = {
                    "jsonrpc": "2.0",
                    "id": json_data["id"],
                    "result": {
                        "os": platform.system(),
                        "os_alias": platform.system_alias(platform.system(), platform.release(), platform.version()),
                        "version": platform.version(),
                        "release": platform.release(),
                        "platform": platform.platform(),
                        "hostname": platform.node(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                    }
                }
                await websocket.send(json.dumps(response))
                continue

            # Unhandled
            response = {
                "jsonrpc": "2.0",
                "id": json_data["id"],
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                }
            }
            await websocket.send(json.dumps(response))
        except Exception:
            response = {
                "jsonrpc": "2.0",
                "id": json_data["id"],
                "result": {
                    "code": -32600	,
                    "message": "InvalidRequest",
                }
            }
            await websocket.send(json.dumps(response))


async def producer_handler(websocket):
    while True:
        await asyncio.sleep(5)
        # message = await producer()
        message = "test"
        broadcast(CONNECTIONS, message)
        # await websocket.send(message)

async def websocket_handler(websocket):
    CONNECTIONS.add(websocket)

    try:
        # async for message in websocket:
        #     print(message)        
        # await websocket.wait_closed()        
        await asyncio.gather(
            consumer_handler(websocket),
            # producer_handler(websocket),
        )
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
        entry.runtime_data.coordinator.update_subscribers[("disks", disk_argument)] = "dummy"  # Would normally be entity_id

    async with serve(websocket_handler, "0.0.0.0", 2604):
        while True:
            new_data = await entry.runtime_data.coordinator._async_update_data()
            new_data = new_data.as_dict()

            notification = {
                "jsonrpc": "2.0",
                "method": "update_data",
                "params": {
                    "data": new_data
                },
            }

            print(json.dumps(notification, indent=2))
            broadcast(CONNECTIONS, json.dumps(notification))

            await asyncio.sleep(DEFAULT_SCAN_INTERVAL)


if __name__ == "__main__":
    """Run server."""
    ## Commandlineoptions
    parser = argparse.ArgumentParser(
        description="Remote SystemMonitor server    ."
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
