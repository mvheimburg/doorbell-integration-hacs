from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .doorbell_hub import DoorbellHub

EVENT_DESC = EventEntityDescription(
    key="doorbell_pressed",
    name="Doorbell",
    device_class=EventDeviceClass.DOORBELL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: DoorbellHub = hass.data[DOMAIN][entry.entry_id]

    entity = DoorbellEventEntity(hub=hub, entry_id=entry.entry_id)
    async_add_entities([entity])


class DoorbellEventEntity(EventEntity):
    """Event entity that fires when the doorbell is pressed."""

    _attr_has_entity_name = True
    _attr_description = EVENT_DESC

    def __init__(self, hub: DoorbellHub, entry_id: str) -> None:
        super().__init__()
        self._hub = hub
        self._attr_unique_id = f"{entry_id}_doorbell"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Doorbell",
            manufacturer="Martin von Heimburg",
            model="RPI4 doorbell",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _bell_pressed() -> None:
            # Fire an event with a basic payload
            self._trigger_event({"timestamp": datetime.utcnow().isoformat()})

        self._hub.register_bell_callback(_bell_pressed)
