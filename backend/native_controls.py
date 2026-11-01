"""Opt-in native setpoint/mode/fan intents; native firmware owns all HVAC loops.

Only allowlisted control scalars are retained. Responses carry partial values,
never raw bucket echoes. Delivery is not confirmation; only accepted native PUT
values update reported state. Nothing is persisted or replayed across restart.
"""

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from backend.native import NativeTelemetry, canonical, envelope, integer
from backend.validation import Invalid, command

FEATURES = {"can_heat", "can_cool", "has_fan"}
MODE_FIELD = "target_temperature_type"
HEAT = {
    "hvac_heater_state",
    "hvac_heat_x2_state",
    "hvac_heat_x3_state",
    "hvac_aux_heater_state",
    "hvac_alt_heat_state",
}
COOL = {"hvac_ac_state", "hvac_cool_x2_state", "hvac_cool_x3_state"}
OUTPUTS = HEAT | COOL | {"hvac_fan_state"}


@dataclass
class Intent:
    ident: str
    key: str
    field: str
    value: object
    revision: int
    expires: float
    sent: bool = False


class NativeControls(NativeTelemetry):
    def __init__(self, core, clock=time.time):
        super().__init__(core, clock)
        self.intents = {}
        self.features = {}
        self.outcomes = {}
        self.notify = lambda _ident: None

    def _records_for(self, ident):
        self.core.caps(ident)
        generation = self.core.registry.data["devices"][ident]["hash"]
        if self._generation.get(ident) != generation:
            self.intents.pop(ident, None)
            self.features.pop(ident, None)
            self.outcomes.pop(ident, None)
        return super()._records_for(ident)

    def capabilities(self, ident):
        self._records_for(ident)
        configured = self.core.caps(ident)
        observed = self.features.get(ident, {})
        modes = ["off"] if "off" in configured["modes"] else []
        for mode, flag in (("heat", "can_heat"), ("cool", "can_cool")):
            if mode in configured["modes"] and observed.get(flag) is True:
                modes.append(mode)
        return {"modes": modes, "fan": configured["fan"] and observed.get("has_fan") is True}

    def action(self, ident):
        self._records_for(ident)
        if not self.core.available(ident):
            return None
        flags = self.features.get(ident, {})
        heating = any(flags.get(k) is True for k in HEAT)
        cooling = any(flags.get(k) is True for k in COOL)
        if heating and cooling:
            return None
        if heating:
            return "heating"
        if cooling:
            return "cooling"
        if flags.get("hvac_fan_state") is True:
            return "fan"
        mode = self.core.states.get(ident, {}).get("mode")
        if mode == "off":
            return "off"
        if mode in ("heat", "cool") and all(flags.get(k) is False for k in OUTPUTS):
            return "idle"
        return None

    def _expire(self, ident):
        now = self.core.clock()
        for op, item in list(self.intents.get(ident, {}).items()):
            if item.expires <= now:
                del self.intents[ident][op]
                self.outcomes.setdefault(ident, {})[op] = "expired"

    def command_status(self, ident):
        self._records_for(ident)
        self._expire(ident)
        return dict(self.outcomes.get(ident, {}))

    def enqueue(self, ident, body):
        self._records_for(ident)
        self._expire(ident)
        validated = command(body, self.capabilities(ident))
        if not self.core.available(ident):
            raise Invalid("device unavailable")
        operation, value = validated["operation"], validated["value"]
        kind, field = "shared", "target_temperature"
        if operation == "mode":
            field = MODE_FIELD
        elif operation == "fan":
            kind, field = "device", "fan_timer_timeout"
            value = 0 if value == "auto" else integer(int(self.clock()) + 600)
        key = f"{kind}.{ident}"
        records = self._records_for(ident)
        previous = records.get(key)
        if previous is None or field not in previous.fingerprints:
            raise Invalid("native control baseline unavailable")
        # A revision supersedes the bucket's earlier intent batch. Retain other
        # still-live intents with the same new revision so disjoint operations
        # are delivered together instead of overwriting one another.
        revision = integer(previous.revision + 1)
        timestamp = integer(max(int(self.clock() * 1000), previous.timestamp + 1))
        previous.revision, previous.timestamp = revision, timestamp
        previous.fingerprints[field] = hmac.digest(
            self._key,
            json.dumps(
                canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode(),
            hashlib.sha256,
        )
        intents = self.intents.setdefault(ident, {})
        for item in intents.values():
            if item.key == key:
                item.revision = revision
        item = Intent(uuid.uuid4().hex, key, field, value, revision, self.core.clock() + 30)
        intents[operation] = item
        self.outcomes.setdefault(ident, {})[operation] = "pending"
        self.notify(ident)
        return {**validated, "id": item.ident, "status": "pending"}

    def _values(self, ident, response):
        self._expire(ident)
        for row in response["objects"]:
            values = {
                i.field: i.value
                for i in self.intents.get(ident, {}).values()
                if i.key == row["object_key"] and i.revision == row["object_revision"]
            }
            if values:
                row["value"] = values
                for item in self.intents[ident].values():
                    if item.key == row["object_key"] and item.revision == row["object_revision"]:
                        item.sent = True
        return response

    def updates(self, ident, body):
        objects = envelope(ident, body, subscription=True)
        records = self._records_for(ident)
        replies = []
        for key, _, _, _, revision, timestamp in objects:
            previous = records.get(key)
            if previous is not None and (
                previous.revision != revision or previous.timestamp != timestamp
            ):
                replies.append(previous.metadata(key))
        return self._values(ident, {"objects": replies})

    def apply(self, ident, body, *, subscription=False):
        objects = envelope(ident, body, subscription=subscription)
        records = self._records_for(ident)
        accepted = {
            key
            for key, _, value, conditional, _, _ in objects
            if value is not None
            and (conditional is None or conditional == getattr(records.get(key), "revision", 0))
        }
        response = super().apply(ident, body, subscription=subscription)
        for key, kind, value, _, _, _ in objects:
            if key not in accepted or value is None:
                continue
            if kind in ("device", "shared"):
                observed = self.features.setdefault(ident, {})
                for name in FEATURES & value.keys():
                    observed[name] = value[name] if type(value[name]) is bool else None
            if kind == "shared":
                observed = self.features.setdefault(ident, {})
                for name in OUTPUTS & value.keys():
                    observed[name] = value[name] if type(value[name]) is bool else None
            projection = {}
            mode = value.get(MODE_FIELD) if kind == "shared" else None
            if isinstance(mode, str) and mode in self.core.caps(ident)["modes"]:
                projection["mode"] = mode
            timeout = value.get("fan_timer_timeout") if kind == "device" else None
            if (
                type(timeout) is int
                and 0 <= timeout <= (1 << 53) - 1
                and self.core.caps(ident)["fan"]
            ):
                projection["fan"] = "on" if timeout > self.clock() else "auto"
            if projection:
                self.core.report(ident, projection)
            for op, item in list(self.intents.get(ident, {}).items()):
                if item.key != key or item.field not in value:
                    continue
                outcome = (
                    "confirmed"
                    if canonical(value[item.field]) == canonical(item.value)
                    else "superseded_by_device"
                )
                self.outcomes.setdefault(ident, {})[op] = outcome
                del self.intents[ident][op]
            # A native telemetry delta may advance this bucket while an unrelated
            # intent waits. Keep its value attached to the current revision,
            # without extending the original deadline or changing reported state.
            for item in self.intents.get(ident, {}).values():
                if item.key == key:
                    item.revision = self._records_for(ident)[key].revision
        self.notify(ident)
        return self._values(ident, response)
