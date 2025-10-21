from __future__ import annotations

import asyncio
import logging

import aiohttp

from .transport_base import JsonRpcBaseTransport

class AioHttpWebsocketClientTransport(JsonRpcBaseTransport):
    def __init__(self) -> None:
        self._clientsession:aiohttp.ClientSession | None = None
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._on_receive_handler = None

    def register_on_receive_handler(self, handler):
        self._on_receive_handler = handler

    async def connect(self, uri, on_disconnect=None):
        self._clientsession = aiohttp.ClientSession()  # TODO: Do we need to keep it or is websocket enough?
        self._websocket = await self._clientsession.ws_connect(uri)
        self._receive_task = asyncio.create_task(self._receive_task_handler(self._websocket))
        self._on_disconnect = on_disconnect
        logging.debug("Transport Connected")

    async def disconnect(self):
        logging.debug("Transport Disconnect")
        if self._websocket:
            await self._websocket.close()
        if self._clientsession:
            await self._clientsession.close()

    async def send(self, message:str):
        logging.debug("Transport Send: %s", message)
        assert self._websocket is not None
        await self._websocket.send_str(message)

    async def _receive_task_handler(self, websocket) -> None:
        while True:
            try:
                message = await websocket.receive()
                # TODO: Handle more message types?
                # CLOSING = 0x100
                # CLOSED = 0x101
                # ERROR = 0x102
                logging.debug(f"Transport receiver -- {message}")

                if message.type == aiohttp.WSMsgType.CLOSE:
                    logging.debug("Connection CLOSE initiated from the other side")
                    continue
                if message.type == aiohttp.WSMsgType.CLOSED:  # This is an aiohttp specific code
                    logging.debug("Connection CLOSED, exiting receive task!!!")
                    if self._on_disconnect:
                        await self._on_disconnect()
                    return
                if message.type == aiohttp.WSMsgType.PING:
                    logging.debug("PING?")
                    continue
                if message.type == aiohttp.WSMsgType.PONG:
                    logging.debug("PONG?")
                    continue
                if message.type == aiohttp.WSMsgType.TEXT:
                    if self._on_receive_handler:
                        await self._on_receive_handler(message.data)
                    continue
            except Exception:
                logging.exception("Exception in websocket receiver")
                return
