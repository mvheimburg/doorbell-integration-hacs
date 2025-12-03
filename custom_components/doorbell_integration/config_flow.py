from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_BASE_TOPIC,
    CONF_CLIENT_ID,
    CONF_DOORBELL_DEVICE_ID,
    CONF_GATE_ENTITY,
    CONF_LOCK_MAP,
    DEFAULT_BASE_TOPIC,
)


def _schema_base(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Base schema: MQTT + doorbell device + real gate entity."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CLIENT_ID,
                default=defaults.get(CONF_CLIENT_ID, "doorbell"),
            ): str,
            vol.Required(
                CONF_BASE_TOPIC,
                default=defaults.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
            ): str,
            vol.Required(
                CONF_DOORBELL_DEVICE_ID,
                default=defaults.get(CONF_DOORBELL_DEVICE_ID),
            ): selector(
                {
                    "device": {
                        # Most likely the MQTT integration
                        "integration": "mqtt",
                    }
                }
            ),
            vol.Optional(
                CONF_GATE_ENTITY,
                default=defaults.get(CONF_GATE_ENTITY),
            ): selector(
                {
                    "entity": {
                        "domain": "cover",
                    }
                }
            ),
        }
    )


class DoorbellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Doorbell integration."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            base_topic = user_input[CONF_BASE_TOPIC].strip()
            doorbell_device_id = user_input.get(CONF_DOORBELL_DEVICE_ID)

            if not client_id:
                errors[CONF_CLIENT_ID] = "client_id_required"
            if not base_topic:
                errors[CONF_BASE_TOPIC] = "base_topic_required"
            if not doorbell_device_id:
                errors[CONF_DOORBELL_DEVICE_ID] = "doorbell_device_required"

            if not errors:
                unique_id = client_id or "doorbell"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                data: dict[str, Any] = {
                    CONF_CLIENT_ID: client_id,
                    CONF_BASE_TOPIC: base_topic,
                    CONF_DOORBELL_DEVICE_ID: doorbell_device_id,
                    CONF_GATE_ENTITY: user_input.get(CONF_GATE_ENTITY),
                    # lock map will be configured later in options
                }

                return self.async_create_entry(
                    title=client_id or "Doorbell",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema_base(user_input),
            errors=errors,
        )

    async def async_step_import(
        self,
        import_config: dict[str, Any],
    ) -> FlowResult:
        """Handle YAML import (optional)."""
        client_id = import_config.get(CONF_CLIENT_ID, "doorbell")
        base_topic = import_config.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)

        await self.async_set_unique_id(client_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=client_id,
            data=import_config
            | {
                CONF_CLIENT_ID: client_id,
                CONF_BASE_TOPIC: base_topic,
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return DoorbellOptionsFlowHandler(config_entry)


class DoorbellOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for an existing Doorbell config entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """
        Manage options:

        - MQTT basics + device + gate
        - Dynamic mapping for any number of lock.doorbell_* entities
        """
        hass: HomeAssistant = self.hass

        # options override data
        raw: dict[str, Any] = {**self._entry.data, **self._entry.options}
        existing_lock_map: dict[str, str] = raw.get(CONF_LOCK_MAP, {}) or {}

        doorbell_device_id = raw.get(CONF_DOORBELL_DEVICE_ID)

        if not doorbell_device_id:
            # If somehow not set, just fall back to base schema without lock mapping
            if user_input is not None:
                return self.async_create_entry(title="", data=user_input)

            base_defaults = {
                CONF_CLIENT_ID: raw.get(CONF_CLIENT_ID, "doorbell"),
                CONF_BASE_TOPIC: raw.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
                CONF_DOORBELL_DEVICE_ID: doorbell_device_id,
                CONF_GATE_ENTITY: raw.get(CONF_GATE_ENTITY),
            }

            return self.async_show_form(
                step_id="init",
                data_schema=_schema_base(base_defaults),
            )

        # Discover remote lock entities on the selected device
        remote_locks = self._get_remote_lock_entities(
            hass=hass,
            device_id=doorbell_device_id,
        )

        if user_input is not None:
            # Split base fields vs dynamic lock map
            new_options: dict[str, Any] = {
                CONF_CLIENT_ID: user_input.get(CONF_CLIENT_ID, raw.get(CONF_CLIENT_ID)),
                CONF_BASE_TOPIC: user_input.get(
                    CONF_BASE_TOPIC,
                    raw.get(CONF_BASE_TOPIC),
                ),
                CONF_DOORBELL_DEVICE_ID: user_input.get(
                    CONF_DOORBELL_DEVICE_ID,
                    doorbell_device_id,
                ),
                CONF_GATE_ENTITY: user_input.get(
                    CONF_GATE_ENTITY,
                    raw.get(CONF_GATE_ENTITY),
                ),
            }

            lock_map: dict[str, str] = {}
            for remote_entity_id in remote_locks:
                mapped = user_input.get(remote_entity_id)
                if mapped:
                    lock_map[remote_entity_id] = mapped

            new_options[CONF_LOCK_MAP] = lock_map

            return self.async_create_entry(
                title="",
                data=new_options,
            )

        # Defaults for base fields
        base_defaults: dict[str, Any] = {
            CONF_CLIENT_ID: raw.get(CONF_CLIENT_ID, "doorbell"),
            CONF_BASE_TOPIC: raw.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
            CONF_DOORBELL_DEVICE_ID: doorbell_device_id,
            CONF_GATE_ENTITY: raw.get(CONF_GATE_ENTITY),
        }

        # Start with base schema and extend it dynamically
        schema_dict: dict[Any, Any] = dict(_schema_base(base_defaults).schema)

        # Dynamically add one selector per doorbell lock
        for remote_entity_id in remote_locks:
            schema_dict[
                vol.Optional(
                    remote_entity_id,
                    default=existing_lock_map.get(remote_entity_id),
                )
            ] = selector(
                {
                    "entity": {
                        "domain": "lock",
                    }
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )

    def _get_remote_lock_entities(
        self,
        hass: HomeAssistant,
        device_id: str,
    ) -> list[str]:
        """Return all lock entity_ids attached to the doorbell device."""
        ent_reg = er.async_get(hass)
        result: list[str] = []

        for entry in ent_reg.entities.values():
            if entry.device_id != device_id:
                continue
            if entry.domain != "lock":
                continue
            # These are your lock.doorbell_* entities
            result.append(entry.entity_id)

        return sorted(result)
