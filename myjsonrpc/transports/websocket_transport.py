from __future__ import annotations

import asyncio
import logging

from .transport_base import JsonRpcBaseTransport

class WebsocketsServerTransport(JsonRpcBaseTransport):
    def __init__(self, websocket, on_disconnect) -> None:
        self._websocket  = websocket
        self._on_receive_handler = None
        self._on_disconnect = on_disconnect

    async def connect(self):
        self._receive_task_ref = asyncio.create_task(self._receive_task(self._websocket))
        logging.debug("Transport Connected")

    async def disconnect(self):
        logging.debug("Transport Disconnect")
        await self._websocket.close()
        self._receive_task_ref = None

    def register_on_receive_handler(self, handler):
        self._on_receive_handler = handler

    async def send(self, message:str):
        logging.debug("Transport Send: %s", message)
        assert self._websocket is not None
        await self._websocket.send(message)

    async def _receive_task(self, websocket) -> None:
        assert self._on_receive_handler is not None
        try:
            async for message in websocket:
                logging.debug(f"Transport receiver -- {message}")
                if self._on_receive_handler is not None:
                    await self._on_receive_handler(message)
                continue
        except Exception:
            logging.exception("Exception in websocket receiver")
            return
        finally:
            await self._on_disconnect()

