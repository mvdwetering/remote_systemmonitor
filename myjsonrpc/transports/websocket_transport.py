#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import asyncio
import logging

class JsonRpcWebsocketsTransport:
    def __init__(self, websocket, on_disconnect) -> None:
        self._websocket  = websocket
        self._on_receive_handler = None
        self._on_disconnect = on_disconnect

    def register_on_receive_handler(self, handler):
        self._on_receive_handler = handler

    async def connect(self):
        assert self._on_receive_handler is not None
        self._receive_task = asyncio.create_task(self._receive_task(self._websocket))
        logging.debug("Backend Connected")

    async def disconnect(self):
        logging.debug("Backend Disconnect")
        await self._websocket.close()

    async def send(self, message:str):
        logging.debug("Backend Send: %s", message)
        assert self._websocket is not None
        await self._websocket.send(message)

    async def _receive_task(self, websocket) -> None:
        try:
            async for message in websocket:
                logging.debug(f"backend receiver -- {message}")
                if self._on_receive_handler:
                    result = await self._on_receive_handler(message)
                    if result is not None:
                        await websocket.send(result)
                continue
        except Exception:
            logging.exception("Exception in websocket receiver")
            return
        finally:
            await self._on_disconnect()
