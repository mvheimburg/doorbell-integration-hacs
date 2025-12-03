from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .doorbell_hub import DoorbellHub

type DoorbellConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Legacy YAML setup (not really used if you rely on config flow)."""
    # You could support configuration.yaml here if you want.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    """Set up Doorbell from a config entry."""
    hub = DoorbellHub(hass=hass, entry=entry)
    await hub.async_setup()

    # Store hub in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hub

    # Forward to platforms (for now only event; later: lock, cover, select)
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["event"],
    )

    # Register services (e.g. doorbell.ring, doorbell.open_gate)
    hub.register_services()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["event"])

    hub: DoorbellHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.async_shutdown()

    return unload_ok
