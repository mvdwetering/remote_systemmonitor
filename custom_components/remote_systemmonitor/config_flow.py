"""Adds config flow for System Monitor."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from awesomeversion import AwesomeVersion
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import slugify

from .const import CONF_PROCESS, DOMAIN
from .rsm_collector_api import RemoteSystemMonitorCollectorApi
from .util import get_all_running_processes

_LOGGER = logging.getLogger(__name__)

MIN_API_VERSION = AwesomeVersion("0.0.2")


USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: dict[str, list] = handler.options.setdefault(BINARY_SENSOR_DOMAIN, {})
    processes = sensors.setdefault(CONF_PROCESS, [])
    previous_processes = processes.copy()
    processes.clear()
    processes.extend(user_input[CONF_PROCESS])

    entity_registry = er.async_get(handler.parent_handler.hass)
    for process in previous_processes:
        if process not in processes and (
            entity_id := entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, slugify(f"binary_process_{process}")
            )
        ):
            entity_registry.async_remove(entity_id)

    return {}


async def get_sensor_setup_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return process sensor setup schema."""
    hass = handler.parent_handler.hass
    # processes = list(await hass.async_add_executor_job(get_all_running_processes, hass))
    processes = list()
    return vol.Schema(
        {
            vol.Required(CONF_PROCESS): SelectSelector(
                SelectSelectorConfig(
                    options=processes,
                    multiple=True,
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            )
        }
    )


async def get_suggested_value(handler: SchemaCommonFlowHandler) -> dict[str, Any]:
    """Return suggested values for sensor setup."""
    sensors: dict[str, list] = handler.options.get(BINARY_SENSOR_DOMAIN, {})
    processes: list[str] = sensors.get(CONF_PROCESS, [])
    return {CONF_PROCESS: processes}


# CONFIG_FLOW = {
#     "user": SchemaFlowFormStep(schema=vol.Schema({})),
# }
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        get_sensor_setup_schema,
        suggested_values=get_suggested_value,
        validate_user_input=validate_sensor_setup,
    )
}


async def validate_input(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.
    Data has the keys from USER_DATA_SCHEMA with values provided by the user.
    """
    collector_api = RemoteSystemMonitorCollectorApi(data[CONF_HOST])
    machine_name = None
    machine_id = None
    try:
        await collector_api.connect()

        api_info = await collector_api.get_api_info()
        if AwesomeVersion(api_info.version) < MIN_API_VERSION:
            raise Exception(f"Unsupported API version: {api_info.version}")

        machine_info = await collector_api.get_machine_info()
        machine_name = machine_info.hostname
        machine_id = machine_info.id
    finally:
        await collector_api.disconnect()

    # Return info that you want to store in the config entry.
    return {"title": machine_name, "unique_id": machine_id}


class SystemMonitorConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for System Monitor."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "System Monitor"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        _LOGGER.debug("async_step_user, %s", user_input)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_DATA_SCHEMA,
            )

        errors = {}

        try:
            info = await validate_input(user_input)
        # TODO: Better exceptions and handling
        # except CannotConnect:
        #     errors["base"] = "cannot_connect"
        # except InvalidAuth:
        #     errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "cannot_connect"
            # errors["base"] = "unknown"
        else:
            # Protect against setting up the same remote host multiple times.
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
