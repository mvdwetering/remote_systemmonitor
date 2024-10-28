"""Utils for System Monitor."""

import logging
from typing import Any

from .coordinator import SystemMonitorCoordinator
from .const import CPU_SENSOR_PREFIXES

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SKIP_DISK_TYPES = {"proc", "tmpfs", "devtmpfs"}


def get_all_disk_mounts(
    hass: HomeAssistant, coordinator: SystemMonitorCoordinator
) -> set[str]:
    """Return all disk mount points on system."""

    _LOGGER.debug("get_all_disk_mounts: %s", coordinator.data)

    disks: set[str] = coordinator.data.disk_usage.keys()

    _LOGGER.debug("Adding disks: %s", ", ".join(disks))
    return disks


def get_all_network_interfaces(
    hass: HomeAssistant, coordinator: SystemMonitorCoordinator
) -> set[str]:
    """Return all network interfaces on system."""
    # Note that this is taking interfaces from iocounters, could also take from addresses?
    # TODO: Figure out if one is better

    interfaces: set[str] = set()
    for interface in  coordinator.data.io_counters.keys():
        if interface.startswith("veth"):
            # Don't load docker virtual network interfaces
            continue
        interfaces.add(interface)
    _LOGGER.debug("Adding interfaces: %s", ", ".join(interfaces))
    return interfaces


def get_all_running_processes(hass: HomeAssistant) -> set[str]:
    """Return all running processes on system."""
    processes: set[str] = set()
    _LOGGER.debug("Running processes: %s", ", ".join(processes))
    return processes


# def read_cpu_temperature(temps: dict[str, list[shwtemp]]) -> float | None:
def read_cpu_temperature(temps: dict[str, Any]) -> float | None:
    """Attempt to read CPU / processor temperature."""
    # entry: shwtemp
    entry: Any

    _LOGGER.debug("CPU Temperatures: %s", temps)
    for name, entries in temps.items():
        for i, entry in enumerate(entries, start=1):
            # In case the label is empty (e.g. on Raspberry PI 4),
            # construct it ourself here based on the sensor key name.
            _label = f"{name} {i}" if not entry.label else entry.label
            # check both name and label because some systems embed cpu# in the
            # name, which makes label not match because label adds cpu# at end.
            if _label in CPU_SENSOR_PREFIXES or name in CPU_SENSOR_PREFIXES:
                return round(entry.current, 1)

    return None
