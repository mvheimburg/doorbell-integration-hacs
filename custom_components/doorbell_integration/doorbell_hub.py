from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import (
    CONF_BASE_TOPIC,
    CONF_CLIENT_ID,
    CONF_DOORBELL_DEVICE_ID,
    CONF_GATE_ENTITY,
    CONF_LOCK_MAP,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
)

type BellCallback = Callable[[], None]
type LockMap = dict[str, str]


@dataclass
class DoorbellHubConfig:
    base_topic: str = DEFAULT_BASE_TOPIC
    client_id: str | None = None
    doorbell_device_id: str | None = None
    gate_entity: str | None = None
    lock_map: LockMap = field(default_factory=dict)


@dataclass
class DoorbellHub:
    """Central object: owns MQTT subscriptions and high-level actions."""

    hass: HomeAssistant
    entry: ConfigEntry
    config: DoorbellHubConfig = field(init=False)

    _bell_callbacks: list[BellCallback] = field(default_factory=list, init=False)

    async def async_setup(self) -> None:
        """Initialize from config entry and subscribe to MQTT topics."""
        self.config = self._parse_entry(self.entry)

        # Subscribe to bell topic
        bell_topic = f"{self.config.base_topic}/bell"

        async def _message_received(msg: mqtt.ReceiveMessage) -> None:
            # Doorbell pressed -> notify listeners
            if msg.payload == "pressed":
                self._notify_bell()

        await mqtt.async_subscribe(
            self.hass,
            bell_topic,
            _message_received,
            1,
        )

    async def async_shutdown(self) -> None:
        """Clean up if necessary."""
        # MQTT subscriptions are cleaned up by HA; no explicit teardown needed.
        return

    @staticmethod
    def _parse_entry(entry: ConfigEntry) -> DoorbellHubConfig:
        """Merge data + options into a single config object."""
        raw: dict[str, Any] = {**entry.data, **entry.options}
        lock_map_raw = raw.get(CONF_LOCK_MAP, {}) or {}
        lock_map: LockMap = {
            k: v
            for k, v in lock_map_raw.items()
            if isinstance(k, str) and isinstance(v, str)
        }

        return DoorbellHubConfig(
            base_topic=raw.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
            client_id=raw.get(CONF_CLIENT_ID),
            doorbell_device_id=raw.get(CONF_DOORBELL_DEVICE_ID),
            gate_entity=raw.get(CONF_GATE_ENTITY),
            lock_map=lock_map,
        )

    # -------- Bell handling -------------------------------------------------

    @callback
    def register_bell_callback(self, cb: BellCallback) -> None:
        self._bell_callbacks.append(cb)

    @callback
    def _notify_bell(self) -> None:
        for cb in list(self._bell_callbacks):
            try:
                cb()
            except Exception:
                # Avoid breaking the chain; log if you want more detail
                continue

    # -------- Actions / services -------------------------------------------

    async def async_ring(self) -> None:
        """Ring the bell via MQTT (test or remote ring)."""
        topic = f"{self.config.base_topic}/bell/cmd"
        await mqtt.async_publish(
            self.hass,
            topic,
            "ring",
            qos=1,
            retain=False,
        )

    async def async_open_gate(self) -> None:
        """Open the mapped real gate entity, if configured."""
        if not self.config.gate_entity:
            return
        await self.hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": self.config.gate_entity},
            blocking=False,
        )

    async def async_close_gate(self) -> None:
        """Close the mapped real gate entity, if configured."""
        if not self.config.gate_entity:
            return
        await self.hass.services.async_call(
            "cover",
            "close_cover",
            {"entity_id": self.config.gate_entity},
            blocking=False,
        )

    async def async_stop_gate(self) -> None:
        """Stop the mapped real gate entity, if configured."""
        if not self.config.gate_entity:
            return

        await self.hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": self.config.gate_entity},
            blocking=False,
        )

    async def async_lock_for_remote(self, remote_entity_id: str) -> None:
        """
        Lock the real entity mapped to a given remote doorbell lock entity.

        remote_entity_id is e.g. 'lock.doorbell_front'.
        """
        real = self.config.lock_map.get(remote_entity_id)
        if not real:
            return
        await self.hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": real},
            blocking=False,
        )

    async def async_unlock_for_remote(self, remote_entity_id: str) -> None:
        """Unlock the real entity mapped to a given remote doorbell lock entity."""
        real = self.config.lock_map.get(remote_entity_id)
        if not real:
            return
        await self.hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": real},
            blocking=False,
        )

    def register_services(self) -> None:
        """Register HA services like doorbell.ring and gate controls."""

        async def _handle_ring(call: ServiceCall) -> None:
            await self.async_ring()

        async def _handle_open_gate(call: ServiceCall) -> None:
            await self.async_open_gate()

        async def _handle_close_gate(call: ServiceCall) -> None:
            await self.async_close_gate()

        async def _handle_stop_gate(call: ServiceCall) -> None:
            await self.async_stop_gate()

        self.hass.services.async_register(
            DOMAIN,
            "ring",
            _handle_ring,
        )
        self.hass.services.async_register(
            DOMAIN,
            "open_gate",
            _handle_open_gate,
        )
        self.hass.services.async_register(
            DOMAIN,
            "close_gate",
            _handle_close_gate,
        )
        self.hass.services.async_register(
            DOMAIN,
            "stop_gate",
            _handle_stop_gate,
        )