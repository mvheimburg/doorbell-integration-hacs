from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .doorbell_hub import DoorbellHub

type DoorbellConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Legacy YAML setup. Optional – can be minimal at first."""
    # You can parse config[DOMAIN] here if you want YAML-based config.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    """Set up Doorbell from a config entry."""
    hub = DoorbellHub(hass=hass, entry=entry)
    await hub.async_setup()

    # Store hub in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hub

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["event"],  # later: "lock", "cover", "select", etc.
    )

    # Register services (e.g. doorbell.ring)
    hub.register_services()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["event"])

    hub: DoorbellHub = hass.data[DOMAIN].pop(entry.entry_id)
    await hub.async_shutdown()

    return unload_ok
