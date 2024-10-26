#!/usr/bin/env python3
"""Server API for Remote System Monitor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import enum
import json
import logging
from typing import Any, Callable, Coroutine
import uuid

from mashumaro.mixins.dict import DataClassDictMixin


@enum.unique
class JsonRpcErrorCode(enum.Enum):
    PARSE_ERROR = (-32700, "Parse error")
    INVALID_REQUEST = (-32600, "Invalid Request")
    METHOD_NOT_FOUND = (-32601, "Method not found")
    INVALID_PARAMS = (-32602, "Invalid method parameters")
    INTERNAL_ERROR = (-32603, "Internal JSON-RPC error")


class JsonRpcResponseError:
    def __init__(
        self, code: JsonRpcErrorCode, data=None
    ) -> None:
        self.code = code
        self.data = None

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self):
        error = {"code": self.code.value[0], "message": self.code.value[1]}
        if self.data:
            error["data"] = self.data
        return error


class JsonRpcResponse:
    def __init__(
        self,
        id: str | int | float | None,
        result=None,
        error: JsonRpcResponseError | None = None,
    ) -> None:
        self.id = id  # id can only be None/Null when id could not be retrieved
        self.result = result
        self.error = error

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self):
        message = {
            "jsonrpc": "2.0",
            "id": self.id,
        }
        if self.result is not None:
            message["result"] = self.result
        if self.error is not None:
            message["error"] = self.error.to_dict()
        return message


class JsonRpc:
    def __init__(self, backend) -> None:
        self._backend = backend
        self._pending_method_calls: dict[str, asyncio.Future] = {}
        self._notification_handlers: dict[str, Callable[[Any], None]] = {}
        self._request_handlers: dict[str, Coroutine[Any, Any, Any]] = {}

        self._request_tasks: set[asyncio.Task] = set()
        self._notification_tasks: set[asyncio.Task] = set()

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
        for task in self._request_tasks:
            task.cancel()
        for task in self._notification_tasks:
            task.cancel()

        # TODO: Is it needed to wait after they have been cancelled?
        await asyncio.gather(*self._request_tasks, return_exceptions=True)
        await asyncio.gather(*self._notification_tasks, return_exceptions=True)

    async def call_method(
        self, method: str, params: Any | None = None
    ) -> JsonRpcResponse:
        logging.debug("Call method: %s, params: %s", method, params)

        id = uuid.uuid4().hex
        message = {
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
        }
        if params:
            message["params"] = params

        # TODO: Add some kind of timeout?
        pending_future: asyncio.Future = asyncio.Future()
        self._pending_method_calls[id] = pending_future

        await self._backend.send(json.dumps(message))
        await pending_future

        return pending_future.result()

    async def send_notification(self, method: str, params: Any | None = None) -> None:
        logging.debug("Call method: %s, params: %s", method, params)

        message = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            message["params"] = params

        await self._backend.send(json.dumps(message))

    async def _handle_request_task(self, id, request_handler, params):
        logging.debug("Handle request handler: %s", params)
        response = await request_handler(*params)

        message = {
            "jsonrpc": "2.0",
            "id": id,
        }

        if response.result is not None:
            message["result"] = response.result
        if response.error is not None:
            message["error"] = response.error.to_dict()

        await self._backend.send(json.dumps(message))
        if task := asyncio.current_task():
            self._request_tasks.remove(task)

    async def _handle_notification_task(self, notification_handler, params):
        logging.debug("Handle notification handler: %s", params)
        notification_handler(params)

    async def _on_receive(self, inbound_message: str) -> str | None:
        logging.debug("On receive, message %s", inbound_message)

        try:
            message = json.loads(inbound_message)

            if isinstance(message, list):
                logging.error(
                    "BATCH request objects not supported yet. Message is ignored"
                )
                return None

            if message.get("jsonrpc", None) != "2.0":
                return str(
                    JsonRpcResponse(
                        id=None,
                        error=JsonRpcResponseError(JsonRpcErrorCode.INVALID_REQUEST),
                    )
                )

            method = message.get("method", None)
            if not isinstance(method, str):
                return str(
                    JsonRpcResponse(
                        id=None,
                        error=JsonRpcResponseError(JsonRpcErrorCode.INVALID_REQUEST),
                    )
                )
            params = message.get(
                "params", None
            )  # TODO: Add more checking, params should be a dict or list
            id = message.get("id", None)
            result = message.get("result", None)
            error = message.get("error", None)

            if method and id is None:
                logging.debug("Notification message received for method: %s", method)
                if notification_handler := self._notification_handlers.get(
                    method, None
                ):
                    try:
                        if isinstance(params, list):
                            result = await notification_handler(*params)
                        elif isinstance(params, dict):
                            result = await notification_handler(**params)
                        elif params is None:
                            result = await notification_handler()
                    except Exception:
                        pass # Just eat it, not responses for notifications


                logging.debug("No notification handler for method: %s", method)
                return None

            if method:
                logging.debug("Request message received for method: %s", method)
                if request_handler := self._request_handlers.get(method, None):
                    # TODO: Maybe requests should be handled an a separate task?
                    try:
                        if isinstance(params, list):
                            result = await request_handler(*params)
                        elif isinstance(params, dict):
                            result = await request_handler(**params)
                        elif params is None:
                            result = await request_handler()
                        else:
                            error = JsonRpcResponseError(JsonRpcErrorCode.INVALID_PARAMS)
                    except Exception:
                        error = JsonRpcResponseError(JsonRpcErrorCode.INTERNAL_ERROR)

                    message = {
                        "jsonrpc": "2.0",
                        "id": id,
                    }

                    return str(JsonRpcResponse(id, result=result, error=error))
                    # if response.result is not None:
                    #     message["result"] = response.result
                    # if response.error is not None:
                    #     message["error"] = response.error.to_dict()                    
                    return message

                logging.debug("No request handler for method: %s", message["method"])
                return str(
                    JsonRpcResponse(
                        id=id,
                        error=JsonRpcResponseError(JsonRpcErrorCode.METHOD_NOT_FOUND),
                    )
                )

            if id and (result or error):
                logging.debug("Response message received for id: %s", id)
                if pending_method_handler := self._pending_method_calls.pop(id, None):
                    pending_method_handler.set_result(JsonRpcResponse(result, error))
                    return None
                else:
                    logging.warning("No pending response handler for id: %s", id)
                    return None

            logging.warning(
                "Invalid JSON-RPC message. Not a request, notification or response... : %s",
                inbound_message,
            )
            return str(
                JsonRpcResponse(
                    id=None,
                    error=JsonRpcResponseError(JsonRpcErrorCode.INVALID_REQUEST),
                )
            )
        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON message: {inbound_message}")

        return str(
            JsonRpcResponse(
                id=None, error=JsonRpcResponseError(JsonRpcErrorCode.PARSE_ERROR)
            )
        )
