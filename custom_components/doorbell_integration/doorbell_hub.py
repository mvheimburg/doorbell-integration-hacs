from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.components import mqtt
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC

type BellCallback = Callable[[], None]


@dataclass
class DoorbellHubConfig:
    base_topic: str = DEFAULT_BASE_TOPIC
    client_id: str | None = None


@dataclass
class DoorbellHub:
    """Central object: owns MQTT subscriptions and exposes high-level actions."""

    hass: HomeAssistant
    entry: ConfigEntry
    config: DoorbellHubConfig = field(init=False)
    _bell_callbacks: list[BellCallback] = field(default_factory=list, init=False)

    async def async_setup(self) -> None:
        """Initialize from entry and subscribe to MQTT topics."""
        self.config = self._parse_entry(self.entry)

        # Subscribe to bell topic
        bell_topic = f"{self.config.base_topic}/bell"

        async def _message_received(
            msg: mqtt.ReceiveMessage,
        ) -> None:
            # Doorbell pressed -> notify listeners
            payload = msg.payload
            if payload == "pressed":
                self._notify_bell()

        await mqtt.async_subscribe(
            self.hass,
            bell_topic,
            _message_received,
            1,
        )

    async def async_shutdown(self) -> None:
        """Clean up if necessary."""
        # Usually nothing needed; mqtt subscriptions are tied to HA lifecycle.
        return

    @staticmethod
    def _parse_entry(entry: ConfigEntry) -> DoorbellHubConfig:
        data: ConfigType = entry.data or {}
        base_topic = data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC)
        client_id = data.get("client_id")
        return DoorbellHubConfig(base_topic=base_topic, client_id=client_id)

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
                # In production you'd use hass.logger here
                continue

    # -------- Actions / services -------------------------------------------

    async def async_ring(self) -> None:
        """Ring the bell via MQTT (test or remote ring)."""
        topic = f"{self.config.base_topic}/bell/cmd"
        await mqtt.async_publish(self.hass, topic, "ring", qos=1, retain=False)

    def register_services(self) -> None:
        """Register HA services like doorbell.ring."""
        async def _handle_ring(call: ServiceCall) -> None:
            await self.async_ring()

        self.hass.services.async_register(
            DOMAIN,
            "ring",
            _handle_ring,
        )
