from __future__ import annotations

DOMAIN = "doorbell"

CONF_BASE_TOPIC = "base_topic"
CONF_CLIENT_ID = "client_id"

DEFAULT_BASE_TOPIC = "doorbell"

# Device that contains cover.doorbell_gate, lock.doorbell_*, select.doorbell_*
CONF_DOORBELL_DEVICE_ID = "doorbell_device_id"

# Single gate target (real gate entity)
CONF_GATE_ENTITY = "gate_entity"

# Dynamic mapping: { remote_lock_entity_id: real_lock_entity_id }
CONF_LOCK_MAP = "lock_map"
