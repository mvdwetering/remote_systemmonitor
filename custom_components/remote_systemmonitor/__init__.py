"""The System Monitor integration."""

import asyncio
from dataclasses import dataclass
import logging

import psutil_home_assistant as ha_psutil

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import (
    CONF_HOST,
)

from .rsm_collector_api import RemoteSystemMonitorCollectorApi

from .coordinator import SystemMonitorCoordinator
# from .util import get_all_disk_mounts

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class SystemMonitorData:
    """Runtime data definition."""

    coordinator: SystemMonitorCoordinator
    psutil_wrapper: ha_psutil.PsutilWrapper
    collector_api: RemoteSystemMonitorCollectorApi


type SystemMonitorConfigEntry = ConfigEntry[SystemMonitorData]


async def async_setup_entry(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> bool:
    """Set up System Monitor from a config entry."""
    psutil_wrapper = await hass.async_add_executor_job(ha_psutil.PsutilWrapper)

    # disk_arguments = list(
    #     await hass.async_add_executor_job(get_all_disk_mounts, hass, psutil_wrapper)
    # )
    # legacy_resources: set[str] = set(entry.options.get("resources", []))
    # for resource in legacy_resources:
    #     if resource.startswith("disk_"):
    #         split_index = resource.rfind("_")
    #         _type = resource[:split_index]
    #         argument = resource[split_index + 1 :]
    #         _LOGGER.debug("Loading legacy %s with argument %s", _type, argument)
    #         disk_arguments.append(argument)

    # _LOGGER.debug("disk arguments to be added: %s", disk_arguments)

    collector_api = RemoteSystemMonitorCollectorApi(entry.data[CONF_HOST])
    try:
        async def on_disconnect():
            # Reload the entry on disconnect.
            # HA will take care of re-init and retries
            await hass.config_entries.async_reload(entry.entry_id)

        await collector_api.connect(on_disconnect=on_disconnect)
        api_info = await collector_api.get_api_info()
        _LOGGER.debug("api_info: %s", api_info)

        # Just make sure the data is there
        await collector_api.get_initial_data()
    except Exception as err:
        await collector_api.disconnect()
        raise ConfigEntryNotReady(err) from err

    initial_data = collector_api._last_data
    disk_arguments = initial_data.disk_usage.keys()

    coordinator: SystemMonitorCoordinator = SystemMonitorCoordinator(
        hass, psutil_wrapper, disk_arguments
    )
    coordinator.async_set_updated_data(initial_data)

    async def on_new_data(data):
        _LOGGER.debug("on_new_data: %s", data)
        coordinator.async_set_updated_data(data)

    collector_api.set_on_new_data_handler(on_new_data)

    # await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SystemMonitorData(coordinator, psutil_wrapper, collector_api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload System Monitor config entry."""
    await entry.runtime_data.collector_api.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )

    return True
