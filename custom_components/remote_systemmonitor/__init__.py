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

from .server_api import RemoteSystemMonitorApi

from .coordinator import SystemMonitorCoordinator
# from .util import get_all_disk_mounts

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class SystemMonitorData:
    """Runtime data definition."""

    coordinator: SystemMonitorCoordinator
    psutil_wrapper: ha_psutil.PsutilWrapper
    server_api: RemoteSystemMonitorApi


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

    server_api = RemoteSystemMonitorApi("127.0.0.1")
    server_api = RemoteSystemMonitorApi(entry.data[CONF_HOST])
    try:
        await server_api.connect()
        # Make sure there has been an update
        # TODO: Improve, just get the data
        await asyncio.sleep(16)
    except Exception as err:
        await server_api.disconnect()
        raise ConfigEntryNotReady(err) from err

    initial_data = server_api._last_data
    disk_arguments = initial_data["disk_usage"].keys()

    coordinator: SystemMonitorCoordinator = SystemMonitorCoordinator(
        hass, psutil_wrapper, disk_arguments
    )
    coordinator.async_set_updated_data(initial_data)

    async def on_new_data(data):
        _LOGGER.debug("on_new_data: %s", data)
        coordinator.async_set_updated_data(data)

    server_api.on_new_data = on_new_data

    # await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SystemMonitorData(coordinator, psutil_wrapper, server_api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload System Monitor config entry."""
    await entry.runtime_data.server_api.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    # if entry.version == 1 and entry.minor_version < 3:
    #     new_options = {**entry.options}
    #     if entry.minor_version == 1:
    #         # Migration copies process sensors to binary sensors
    #         # Repair will remove sensors when user submit the fix
    #         if processes := entry.options.get(SENSOR_DOMAIN):
    #             new_options[BINARY_SENSOR_DOMAIN] = processes
    #     hass.config_entries.async_update_entry(
    #         entry, options=new_options, version=1, minor_version=2
    #     )

    #     if entry.minor_version == 2:
    #         new_options = {**entry.options}
    #         if SENSOR_DOMAIN in new_options:
    #             new_options.pop(SENSOR_DOMAIN)
    #         hass.config_entries.async_update_entry(
    #             entry, options=new_options, version=1, minor_version=3
    #         )

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )

    return True
