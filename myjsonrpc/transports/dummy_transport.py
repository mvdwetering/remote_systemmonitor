from __future__ import annotations

import logging


class JsonRpcDummyTransport:
    """
    This transport is a dummy and does not connect to a server. It is only used for testing.
    """

    def __init__(self) -> None:
        self._on_receive_handler = None
        self.sent_messages: list[str] = []

    def register_on_receive_handler(self, handler):
        self._on_receive_handler = handler

    async def send(self, message: str):
        logging.debug("Transport send: %s", message)
        self.sent_messages.append(message)

    async def call_receive(self, message: str):
        if self._on_receive_handler:
            await self._on_receive_handler(message)

    def last_sent_message(self) -> str | None:
        if self.sent_messages:
            return self.sent_messages[-1]
        return None