from __future__ import annotations

from dataclasses import dataclass
import importlib.util  # It is here to load for ha_psutil which seems to be missing it, but does need it  # noqa: F401
import logging

from server.coordinator import SystemMonitorCoordinator
from server.hass_stubs import ConfigEntry, HomeAssistant
from server.util import get_all_disk_mounts
import psutil_home_assistant as ha_psutil



_LOGGER = logging.getLogger(__name__)

@dataclass
class SystemMonitorData:
    """Runtime data definition."""

    coordinator: SystemMonitorCoordinator
    psutil_wrapper: ha_psutil.PsutilWrapper
    
type SystemMonitorConfigEntry = ConfigEntry[SystemMonitorData]

async def async_setup_entry(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> bool:
    """Set up System Monitor from a config entry."""
    psutil_wrapper = await hass.async_add_executor_job(ha_psutil.PsutilWrapper)

    disk_arguments = list(
        await hass.async_add_executor_job(get_all_disk_mounts, hass, psutil_wrapper)
    )
    # legacy_resources: set[str] = set(entry.options.get("resources", []))
    # for resource in legacy_resources:
    #     if resource.startswith("disk_"):
    #         split_index = resource.rfind("_")
    #         _type = resource[:split_index]
    #         argument = resource[split_index + 1 :]
    #         _LOGGER.debug("Loading legacy %s with argument %s", _type, argument)
    #         disk_arguments.append(argument)

    _LOGGER.debug("disk arguments to be added: %s", disk_arguments)

    coordinator: SystemMonitorCoordinator = SystemMonitorCoordinator(
        hass, psutil_wrapper, disk_arguments
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SystemMonitorData(coordinator, psutil_wrapper)

    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # entry.async_on_unload(entry.add_update_listener(update_listener))
    return True