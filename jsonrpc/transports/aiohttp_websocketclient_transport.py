#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

class JsonRpcAioHttpWebsocketClientTransport:
    def __init__(self) -> None:
        self._clientsession:aiohttp.ClientSession | None = None
        self._websocket: aiohttp.ClientWebSocketResponse | None = None
        self._on_receive_handler = None

    def register_on_receive_handler(self, handler):
        self._on_receive_handler = handler

    async def connect(self, uri):
        assert self._on_receive_handler is not None

        self._clientsession = aiohttp.ClientSession()  # TODO: Do we need to keep it or is websocket enough?
        self._websocket = await self._clientsession.ws_connect(uri)
        self._receive_task = asyncio.create_task(self._receive_task(self._websocket))
        logging.debug("Backend Connected")

    async def disconnect(self):
        logging.debug("Backend Disconnect")
        if self._websocket:
            await self._websocket.close()
        if self._clientsession:
            await self._clientsession.close()

    async def send(self, message:str):
        logging.debug("Backend Send: %s", message)
        assert self._websocket is not None
        await self._websocket.send_str(message)

    async def _receive_task(self, websocket) -> None:
        while True:
            try:
                message = await websocket.receive()
                # TODO: Handle more message types?
                # CLOSING = 0x100
                # CLOSED = 0x101
                # ERROR = 0x102
                logging.debug(f"backend receiver -- {message}")

                if message.type == aiohttp.WSMsgType.CLOSE:
                    logging.warning("Connection CLOSE initiated from the other side")
                    continue
                if message.type == aiohttp.WSMsgType.CLOSED:  # This is an aiohttp specific code
                    logging.warning("Connection CLOSED, exiting receive task!!!")
                    return
                if message.type == aiohttp.WSMsgType.PING:
                    logging.warning("PING?")
                    continue
                if message.type == aiohttp.WSMsgType.PONG:
                    logging.warning("PONG?")
                    continue
                if message.type == aiohttp.WSMsgType.TEXT:
                    if self._on_receive_handler:
                        self._on_receive_handler(message.data)
                    continue
            except Exception as err:
                logging.exception("Exception in websocket receiver")
                return
