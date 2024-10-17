#!/usr/bin/env python3
"""Server for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from websockets.asyncio.server import broadcast, serve

from server import async_setup_entry
from server.hass_stubs import DEFAULT_SCAN_INTERVAL, ConfigEntry, HomeAssistant

CONNECTIONS = set()

async def consumer_handler(websocket):
    async for message in websocket:
        print(message)

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

    async with serve(websocket_handler, "localhost", 2604):
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
