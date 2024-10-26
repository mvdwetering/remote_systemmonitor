#!/usr/bin/env python3
"""JSON-RPC 2.0 implementation."""

from __future__ import annotations

import asyncio
import enum
import json
import logging
from typing import Any, Callable, Coroutine
import uuid


@enum.unique
class JsonRpcErrorCode(enum.Enum):
    PARSE_ERROR = (-32700, "Parse error")
    INVALID_REQUEST = (-32600, "Invalid Request")
    METHOD_NOT_FOUND = (-32601, "Method not found")
    INVALID_PARAMS = (-32602, "Invalid method parameters")
    INTERNAL_ERROR = (-32603, "Internal JSON-RPC error")


class JsonRpcResponseError:
    def __init__(self, code: JsonRpcErrorCode, data=None) -> None:
        self.code = code
        self.data = data

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
        result: Any = None,
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


class JsonRpcNotification:
    def __init__(
        self,
        method: str,
        params: list | dict | None = None,
    ) -> None:
        self.method = method
        self.params = params

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self):
        message = {
            "jsonrpc": "2.0",
            "method": self.method,
        }
        if self.params is not None:
            message["params"] = self.params
        return message


class JsonRpcRequest(JsonRpcNotification):
    def __init__(
        self,
        method: str,
        params: list | dict | None = None,
    ) -> None:
        self._id = uuid.uuid4().hex
        super().__init__(method, params)

    @property
    def id(self) -> str:
        return self._id

    def to_dict(self):
        message = super().to_dict()
        message["id"] = self._id
        return message


class JsonRpc:
    def __init__(self, backend) -> None:
        self._backend = backend
        self._pending_method_calls: dict[str, asyncio.Future] = {}
        self._notification_handlers: dict[str, Callable[[Any], None]] = {}
        self._request_handlers: dict[str, Coroutine[Any, Any, Any]] = {}

        backend.register_on_receive_handler(self._on_receive)

    def register_notification_handler(self, method, handler):
        self._notification_handlers[method] = handler

    def register_request_handler(self, method, handler):
        self._request_handlers[method] = handler

    async def call_method(
        self, method: str, params: Any | None = None
    ) -> JsonRpcResponse:
        logging.debug("Call method: %s, params: %s", method, params)

        pending_future: asyncio.Future = asyncio.Future()

        request = JsonRpcRequest(method, params)
        self._pending_method_calls[request.id] = pending_future

        await self._backend.send(str(request))

        # TODO: Add some kind of timeout?
        await pending_future
        return pending_future.result()

    async def send_notification(self, method: str, params: Any | None = None) -> None:
        logging.debug("Send notification, method: %s, params: %s", method, params)
        await self._backend.send(str(JsonRpcNotification(method, params)))

    async def _handle_notification(self, method, params):
        notification_handler = self._notification_handlers.get(method, None)
        if notification_handler is None:
            logging.debug("No notification handler for method: %s", method)
            return None

        try:
            if isinstance(params, list):
                await notification_handler(*params)
            elif isinstance(params, dict):
                await notification_handler(**params)
            elif params is None:
                await notification_handler()
        except Exception:
            logging.exception("Exception in notification handler")

        # No responses for notifications
        return None

    async def _handle_request(self, id, method, params):
        request_handler = self._request_handlers.get(method, None)
        if request_handler is None:
            logging.debug("No request handler for method: %s", method)
            return str(
                JsonRpcResponse(
                    id=id,
                    error=JsonRpcResponseError(JsonRpcErrorCode.METHOD_NOT_FOUND),
                )
            )

        # TODO: Maybe requests should be handled an a separate task?
        result = None
        error = None
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

        return str(JsonRpcResponse(id, result=result, error=error))

    async def _handle_response(self, id, result, error):
        if pending_method_handler := self._pending_method_calls.pop(id, None):
            pending_method_handler.set_result(JsonRpcResponse(id, result, error))
            return None

        logging.warning("No pending response handler for id: %s", id)
        return None

    async def _on_receive(self, inbound_message: str) -> str | None:
        logging.debug("On receive, message %s", inbound_message)

        try:
            message = json.loads(inbound_message)
        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON message: {inbound_message}")

            return str(
                JsonRpcResponse(
                    id=None, error=JsonRpcResponseError(JsonRpcErrorCode.PARSE_ERROR)
                )
            )

        if isinstance(message, list):
            logging.warning(
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
        if method and not isinstance(method, str):
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
            response = await self._handle_notification(method, params)
            return response

        if method:
            logging.debug("Request message received for method: %s", method)
            response = await self._handle_request(id, method, params)
            return response

        if id and (result or error):
            logging.debug(
                "Response message received for id: %s, result: %s, error: %s",
                id,
                result,
                error,
            )
            response = await self._handle_response(id, result=result, error=error)
            return response

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
