"""
Dummy HomeAssistant implementations for the server.
Intended to keep changes of copied code limited, so it will be easier to update in the future
"""
import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Awaitable, Callable, Generic
from typing_extensions import TypeVar


DEFAULT_SCAN_INTERVAL = 15

class HomeAssistant():

    def __init__(self):
        self.loop = asyncio.get_event_loop()

#    @callback
    def async_add_executor_job[*_Ts, _T](
        self, target: Callable[[*_Ts], _T], *args: *_Ts
    ) -> asyncio.Future[_T]:
        """Add an executor job from within the event loop."""
        task = self.loop.run_in_executor(None, target, *args)

        # tracked = asyncio.current_task() in self._tasks
        # task_bucket = self._tasks if tracked else self._background_tasks
        # task_bucket.add(task)
        # task.add_done_callback(task_bucket.remove)

        return task


_DataT = TypeVar("_DataT", default=dict[str, Any])

class DataUpdateCoordinator(Generic[_DataT]):

    def __init__(
                 
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[_DataT]] | None = None,
        setup_method: Callable[[], Awaitable[None]] | None = None,
        # request_refresh_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None,
        always_update: bool = True,                 
                 ) -> None:
        self.hass = hass

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""
        # if self.update_method is None:
        raise NotImplementedError("Update method not implemented")
        # return await self.update_method()

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Will automatically raise ConfigEntryNotReady if the refresh
        fails. Additionally logging is handled by config entry setup
        to ensure that multiple retries do not cause log spam.
        """
        # if await self.__wrap_async_setup():
        #     await self._async_refresh(
        #         log_failures=False, raise_on_auth_failed=True, raise_on_entry_error=True
        #     )
        #     if self.last_update_success:
        #         return
        # ex = ConfigEntryNotReady()
        # ex.__cause__ = self.last_exception
        # raise ex
        await self._async_update_data()

class TimestampDataUpdateCoordinator(DataUpdateCoordinator[_DataT]):
    pass


class dt():

    @staticmethod
    def utc_from_timestamp(timestamp) -> datetime:
        return datetime.fromtimestamp(timestamp, tz=UTC)



class ConfigEntry(Generic[_DataT]):
    runtime_data: _DataT

    def __init__(
        self) -> None:
        pass