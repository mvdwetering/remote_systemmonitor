#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class JsonRpcBaseTransport(ABC):
    """
    Transports should derive from this class. It mainly exists to force implementation of abstract members.
    """
    @abstractmethod
    def register_on_receive_handler(self, handler: Callable[[str], Awaitable[None]]):
        """Register a handler which will handle JSONRPC messages received by the transport."""
        pass

    @abstractmethod
    async def send(self, message: str):
        """Send the, already formatted, JSONRPC message over the transport."""
        pass

