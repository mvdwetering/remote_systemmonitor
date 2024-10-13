#!/usr/bin/env python3
"""Server for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import logging

from server import async_setup_entry
from server.hass_stubs import DEFAULT_SCAN_INTERVAL, ConfigEntry, HomeAssistant



async def main(args):
    hass = HomeAssistant()
    entry = ConfigEntry()

    await async_setup_entry(hass, entry)

    assert entry.runtime_data is not None
    while True:
        new_data = await entry.runtime_data.coordinator._async_update_data()
        print(new_data)

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
