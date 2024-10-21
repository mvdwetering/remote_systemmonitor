#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine
import uuid

import aiohttp

DEFAULT_PORT = 2604

class JsonRpcAioHttpWebsocketBackend:
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

class JsonRpcResponseError:
    def __init__(self, code:int, message:str) -> None:
        self.code = code
        self.message = message

class JsonRpcResponse:
    def __init__(self, result=None, error:JsonRpcResponseError|None=None) -> None:
        self.result = result
        self.error = error

class JsonRpc:
    def __init__(self, backend) -> None:
        self._backend = backend
        self._pending_method_calls: dict[str, asyncio.Future] = {}
        self._notification_handlers: dict[str, Callable[[Any], None]] = {}
        self._request_handlers: dict[str, Coroutine[Any, Any, JsonRpcResponse]] = {}

        self._request_tasks: set[asyncio.Task] = set()

        backend.register_on_receive_handler(self._on_receive)

    def register_notification_handler(self, method, handler):
        self._notification_handlers[method] = handler

    def register_request_handler(self, method, handler):
        """
        Register a request handler for a method.
        Note that this is UNTESTED !!!
        """	
        self._request_handlers[method] = handler

    async def connect(self, uri):
        await self._backend.connect(uri)

    async def disconnect(self):
        await self._backend.disconnect()


    async def call_method(self, method:str, params:Any|None=None) -> JsonRpcResponse:
        logging.debug("Call method: %s, params: %s", method, params)

        id = uuid.uuid4().hex
        message = {
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
        }
        if params:
            message["params"] = params

        pending_future: asyncio.Future = asyncio.Future()
        self._pending_method_calls[id] = pending_future
    
        await self._backend.send(json.dumps(message))

        await pending_future

        return pending_future.result()

    async def _handle_request_task(self, id, request_handler, params):
        logging.debug("Handle request handler: %s", params)
        response = await request_handler(params)

        message = {
            "jsonrpc": "2.0",
            "id": id,
        }

        if response.result is not None:
            message["result"] = response.result
        if response.error is not None:
            message["error"] = response.error

        await self._backend.send(json.dumps(message))

    def _on_receive(self, inbound_message:str):
        logging.debug("On receive, message %s", inbound_message)

        try:
            message = json.loads(inbound_message)
            if message["jsonrpc"] != "2.0":
                raise Exception("Invalid JSON-RPC data")

            id = message.get("id", None)
            if id is None:
                logging.debug("Notification message received")
                if notification_handler := self._notification_handlers.get(message["method"], None):
                    notification_handler(message.get("params", None))
                else:
                    logging.debug("No notification handler for method: %s", message["method"])
                return

            if method := message.get("method", None):
                if request_handler := self._request_handlers.get(method, None):
                    # NOTE: Requests handling is UNTESTED !!!
                    request_task = asyncio.create_task(self._handle_request_task( id, request_handler, message.get("params", None)))
                    self._request_tasks.add(request_task)
                else:
                    logging.debug("No request handler for method: %s", message["method"])
                return

            result = message.get("result", None)
            error = message.get("error", None)

            if result or error:
                if pending_method_handler := self._pending_method_calls.pop(id, None):
                    pending_method_handler.set_result(JsonRpcResponse(result, error))
                else:
                    logging.warning("No pending response handler for id: %s", id)
                return
            
            logging.warning("Invalid JSON-RPC message. Not a request, notification or response... : %s", inbound_message)

        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON message: {inbound_message}")
            return

class ApiInfo:
    def __init__(self, version:str, id:str) -> None:
        self.version = version
        self.id = id
        if id != "RemoteSystemMonitorApi":
            raise Exception("Invalid API id: %s. This is not a RemoteSystemMonitorApi!", id)

    def __str__(self):
        return f"Version: {self.version}"

    @staticmethod
    def from_jsonrpc(result):
        return ApiInfo(result["version"], result["id"])

class RemoteSystemMonitorApi:
    def __init__(self, host: str, port: int = DEFAULT_PORT, on_new_data=None) -> None:
        self.host = host
        self.port = port
        self.on_new_data = on_new_data
        # self._clientsession: aiohttp.ClientSession | None = None
        # self._websocket: aiohttp.ClientWebSocketResponse | None = None
        # self._receive_task: asyncio.Task | None = None
        # self._last_data: dict | None = None

        # TODO: Need to do something with disconnects/connection errors, probably on backend??
        self._backend = JsonRpcAioHttpWebsocketBackend()
        self._jsonrpc = JsonRpc(self._backend)

    async def connect(self):
        uri = f"ws://{self.host}:{self.port}"
        await self._jsonrpc.connect(uri)
        # self._clientsession = aiohttp.ClientSession()
        # self._websocket = await self._clientsession.ws_connect(uri)
        # self._receive_task = asyncio.create_task(self._receiver())
        self._jsonrpc.register_notification_handler("update_data", self.on_new_data)
        logging.debug("Connected")


    async def disconnect(self):
        logging.debug("Disconnect")
        await self._backend.disconnect()
        # if self._websocket:
        #     await self._websocket.close()
        # if self._clientsession:
        #     await self._clientsession.close()

    async def get_api_info(self) -> ApiInfo:
        assert self._jsonrpc is not None
        response = await self._jsonrpc.call_method("get_api_info")

        if response.error is not None:
            raise Exception(f"Error: {response.error}")
        return ApiInfo.from_jsonrpc(response.result)


async def main(args):

    data_received = 0

    def on_new_data(params):
        nonlocal data_received
        print(f"### THE DATA ### -- {params['data']}")
        data_received = data_received + 1

    api = RemoteSystemMonitorApi(args.host, args.port, on_new_data=on_new_data)
    await api.connect()

    api_info = await api.get_api_info()
    print(api_info)


    while True:
        await asyncio.sleep(5)
        print(".")
        if data_received > 2:
            print("\n** ENOUGH DATA WAS RECEIVED, DISCONNECTING **")
            await api.disconnect()
            return


if __name__ == "__main__":

    ## Commandlineoptions
    parser = argparse.ArgumentParser(description="Remote SystemMonitor client API.")
    parser.add_argument(
        "host",
        type=str,
        help="The hostname or IP of the server to connect to.",
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
