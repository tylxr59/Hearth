"""Opt-in native setpoint/mode/fan intents; native firmware owns all HVAC loops.

Only allowlisted control scalars are retained. Responses carry partial values,
never raw bucket echoes. Delivery is not confirmation; only accepted native PUT
values update reported state. Control intents are never persisted or replayed.
Reported-state caching and explicit local-user configuration are separate.
"""

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field

from backend import native_features, native_pairing, reported_state
from backend.native import NativeTelemetry, canonical, envelope, has_empty_filters, integer
from backend.validation import Invalid, command, number

FEATURES = {"can_heat", "can_cool", "has_fan", "has_emer_heat"}
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
    extra_values: dict = field(default_factory=dict)

    def desired(self):
        return {self.field: self.value, **self.extra_values}


class NativeControls(NativeTelemetry):
    def __init__(self, core, clock=time.time):
        super().__init__(core, clock)
        self.intents = {}
        self.features = {}
        self.outcomes = {}
        self.reported = {}
        self.restored_fields = {}
        self.reported_changed = lambda _ident: None
        self.requests = {}
        self.last_request = {}
        self.notify = lambda _ident: None
        self._local_users = {}
        self._local_user_offered = set()
        self._local_user_acknowledged = set()

    def _records_for(self, ident):
        self.core.caps(ident)
        generation = self.core.registry.data["devices"][ident]["hash"]
        if self._generation.get(ident) != generation:
            self.intents.pop(ident, None)
            self.features.pop(ident, None)
            self.outcomes.pop(ident, None)
            self.reported.pop(ident, None)
            self.restored_fields.pop(ident, None)
            self.requests.pop(ident, None)
            self.last_request.pop(ident, None)
            self._local_users.pop(ident, None)
            self._local_user_offered.discard(ident)
            self._local_user_acknowledged.discard(ident)
        return super()._records_for(ident)

    def home_key(self, ident):
        value = self.reported.get(ident, {}).get("device", {}).get("values", {}).get("structure_id")
        return native_features.structure_key(value) if value is not None else None

    def normalize(self, ident, body, *, subscription=False):
        # A home bucket is scoped to this authenticated device's record namespace.
        # Only its accepted device-bucket reference can select it; never expose
        # account buckets globally or infer ownership from a structure upload.
        self._records_for(ident)
        home = self.home_key(ident)
        rows = envelope(ident, body, subscription=subscription)
        records = self._records_for(ident)
        for key, kind, value, conditional, _, _ in rows:
            if kind != "device" or not value or "structure_id" not in value:
                continue
            if conditional is not None and conditional != getattr(records.get(key), "revision", 0):
                continue
            try:
                home = native_features.structure_key(value["structure_id"])
            except Invalid:
                home = None
        user = self._local_users.get(ident) if subscription else None
        user_key = native_pairing.metadata(user)["object_key"] if user is not None else None
        result = envelope(
            ident, body, subscription=subscription, structure_key=home, user_key=user_key
        )
        self._empty_filters_accepted |= subscription and has_empty_filters(body)
        # User configuration stays separate from observed device buckets. Validate
        # its metadata before any mutation, then leave its values unretained.
        return [row for row in result if row[1] != "user"]

    def configure_local_users(self, data):
        data = native_pairing.validate(data)
        for ident, record in data["devices"].items():
            enrolled = self.core.registry.data["devices"].get(ident)
            if enrolled is None or enrolled["hash"] != record["generation"]:
                continue
            self._records_for(ident)
            self._local_users[ident] = dict(record)
            self._local_user_offered.discard(ident)
            self._local_user_acknowledged.discard(ident)
            self.notify(ident)

    def local_user_view(self, ident):
        self._records_for(ident)
        return {
            "configured": ident in self._local_users,
            "offered": ident in self._local_user_offered,
            "metadata_acknowledged": ident in self._local_user_acknowledged,
        }

    def _local_user_response(self, ident, body, response):
        record = self._local_users.get(ident)
        if record is None:
            return response
        meta = native_pairing.metadata(record)
        rows = envelope(
            ident,
            body,
            subscription=True,
            structure_key=self.home_key(ident),
            user_key=meta["object_key"],
        )
        own = next((row for row in rows if row[0] == meta["object_key"]), None)
        matches = own is not None and own[4:] == (meta["object_revision"], meta["object_timestamp"])
        if matches:
            self._local_user_acknowledged.add(ident)
        # One offer after configuration/server reload. Thereafter resend only
        # on an explicit request for our user key with different metadata.
        # Missing acknowledgement does not create an unbounded push loop.
        if ident in self._local_user_offered and (own is None or matches):
            return response
        self._local_user_offered.add(ident)
        return {"objects": [native_pairing.announcement(record), *response["objects"]]}

    def bootstrap_listing(self, ident):
        response = self.listing(ident)
        record = self._local_users.get(ident)
        if record is not None:
            response["objects"][0] = native_pairing.announcement(record)
            self._local_user_offered.add(ident)
            self._local_user_acknowledged.discard(ident)
        return response

    def listing(self, ident):
        response = super().listing(ident)
        record = self._local_users.get(ident)
        if record is not None:
            response["objects"].insert(0, native_pairing.metadata(record))
        return response

    def snapshot_reported(self):
        return reported_state.snapshot(self, integer(int(self.clock() * 1000)))

    def restore_reported(self, data):
        return reported_state.restore(self, data)

    def state_source(self, ident, field):
        self._records_for(ident)
        records = self.reported.get(ident, {})
        shared = records.get("shared", {}).get("values", {})
        source = {
            "temperature": (
                "shared" if "current_temperature" in shared else "device",
                "current_temperature",
            ),
            "humidity": ("device", "current_humidity"),
            "target_temperature": ("shared", "target_temperature"),
            "target_temperature_low": ("shared", "target_temperature_low"),
            "target_temperature_high": ("shared", "target_temperature_high"),
            "mode": ("shared", MODE_FIELD),
            "fan": ("device", "fan_timer_timeout"),
        }.get(field)
        if source is None or source[1] not in records.get(source[0], {}).get("values", {}):
            return "unknown"
        return "cache" if source in self.restored_fields.get(ident, set()) else "device"

    def note_request(self, ident, kind):
        self._records_for(ident)
        if kind not in ("put", "subscribe", "get"):
            raise Invalid("unknown native request category")
        counters = self.requests.setdefault(ident, {})
        counters[kind] = min(counters.get(kind, 0) + 1, 2147483647)
        self.last_request[ident] = self.core.clock()

    def control_view(self, ident):
        records = self._records_for(ident)
        self._expire(ident)
        shared = records.get(f"shared.{ident}")
        device = records.get(f"device.{ident}")
        return {
            "capabilities": self.capabilities(ident),
            "command_status": self.command_status(ident),
            "pending": {
                op: {
                    "offered": i.sent,
                    "seconds_remaining": max(0, round(i.expires - self.core.clock(), 1)),
                }
                for op, i in self.intents.get(ident, {}).items()
            },
            "requests": dict(self.requests.get(ident, {})),
            "last_request_age": max(0, round(self.core.clock() - self.last_request[ident], 1))
            if ident in self.last_request
            else None,
            "feature_baselines": {
                "home_reference_observed": device is not None
                and "structure_id" in device.fingerprints,
                "home_reference_validated": self.home_key(ident) is not None,
                "native_eco_field_observed": device is not None and "eco" in device.fingerprints,
                "schedule_bucket_observed": f"schedule.{ident}" in records,
                "schedule_schema_validated": bool(self.reported.get(ident, {}).get("schedule")),
                "schedule_fresh": bool(self.reported.get(ident, {}).get("schedule"))
                and not any(
                    kind == "schedule" for kind, _ in self.restored_fields.get(ident, set())
                ),
                "observed_bucket_kinds": sorted({key.partition(".")[0] for key in records}),
            },
            "local_pairing": self.local_user_view(ident),
            "baseline_fields": {
                "temperature": shared is not None and "target_temperature" in shared.fingerprints,
                "mode": shared is not None and MODE_FIELD in shared.fingerprints,
                "fan": device is not None and "fan_timer_timeout" in device.fingerprints,
            },
        }

    def capabilities(self, ident):
        self._records_for(ident)
        configured = self.core.caps(ident)
        observed = self.features.get(ident, {})
        modes = ["off"] if "off" in configured["modes"] else []
        for mode, flag in (("heat", "can_heat"), ("cool", "can_cool")):
            if mode in configured["modes"] and observed.get(flag) is True:
                modes.append(mode)
        if "heat_cool" in configured["modes"] and {"heat", "cool"} <= set(modes):
            modes.append("heat_cool")
        if (
            "emergency" in configured["modes"]
            and "heat" in modes
            and observed.get("has_emer_heat") is True
        ):
            modes.append("emergency")
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
        if mode in ("heat", "cool", "heat_cool") and all(flags.get(k) is False for k in OUTPUTS):
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

    def advanced_plan(self, ident, body, schedule_backed_up):
        if not isinstance(body, dict) or body.get("operation") not in (
            "eco",
            "eco_temperatures",
            "schedule",
            "schedule_mode",
        ):
            return None
        op = body["operation"]
        if set(body) != (
            {"operation", "value", "expected_revision"}
            if op == "schedule"
            else {"operation", "value"}
        ):
            raise Invalid("invalid native feature command")
        value = body["value"]
        if op == "eco":
            if type(value) is not bool or self.home_key(ident) is None:
                raise Invalid("eco requires a reported home reference and boolean")
            original = self.reported.get(ident, {}).get("structure", {}).get("values", {})
            if (
                type(original.get("manual_eco_all")) is not bool
                or type(original.get("manual_eco_timestamp")) is not int
            ):
                raise Invalid("validated native eco baseline required")
            return (
                "structure",
                "manual_eco_all",
                value,
                {"manual_eco_timestamp": integer(int(self.clock()))},
            )
        if op == "eco_temperatures":
            bounds = native_features.eco_temperatures(value)
            if not {"heat", "cool"} <= set(self.capabilities(ident)["modes"]):
                raise Invalid(
                    "both heating and cooling capabilities required for paired eco bounds"
                )
            return (
                "device",
                "away_temperature_low",
                bounds["away_temperature_low"],
                {"away_temperature_high": bounds["away_temperature_high"]},
            )
        if op == "schedule_mode":
            if not isinstance(value, str) or value not in native_features.MODES:
                raise Invalid("supported schedule mode required")
            if native_features.MODES[value] not in self.capabilities(ident)["modes"]:
                raise Invalid("schedule mode unsupported by reported equipment")
            return "shared", "schedule_mode", value, {}
        normalized = native_features.schedule(value)
        if (
            native_features.MODES[normalized["schedule_mode"]]
            not in self.capabilities(ident)["modes"]
        ):
            raise Invalid("schedule mode unsupported by reported equipment")
        record = self._records_for(ident).get(f"schedule.{ident}")
        if record is None or integer(body["expected_revision"]) != record.revision:
            raise Invalid("schedule changed; read and back up the current week again")
        baseline = self.reported.get(ident, {}).get("schedule", {}).get("values", {})
        native_features.schedule_record(baseline)
        if any(kind == "schedule" for kind, _ in self.restored_fields.get(ident, set())):
            raise Invalid("a fresh native weekly schedule report is required before replacement")
        if not schedule_backed_up:
            raise Invalid("use the HA schedule action to preserve the current week first")
        if "manual_schedule" in baseline:
            return "schedule", "manual_schedule", normalized, {}
        return "schedule", "ver", 2, {k: v for k, v in normalized.items() if k != "ver"}

    def enqueue(self, ident, body, *, schedule_backed_up=False):
        self._records_for(ident)
        self._expire(ident)
        caps = self.capabilities(ident)
        advanced = self.advanced_plan(ident, body, schedule_backed_up)
        if advanced is not None:
            validated = {"operation": body["operation"], "value": body["value"]}
        elif isinstance(body, dict) and body.get("operation") == "temperature_range":
            if (
                set(body) != {"operation", "value"}
                or not isinstance(body["value"], dict)
                or set(body["value"]) != {"low", "high"}
            ):
                raise Invalid("both range targets required")
            if (
                "heat_cool" not in caps["modes"]
                or self.core.states.get(ident, {}).get("mode") != "heat_cool"
            ):
                raise Invalid("active supported heat/cool mode required")
            low = number(body["value"]["low"], 10, 30)
            high = number(body["value"]["high"], 10, 30)
            if low >= high:
                raise Invalid("low range target must be below high target")
            validated = {"operation": "temperature_range", "value": {"low": low, "high": high}}
        else:
            validated = command(body, caps)
            if (
                validated["operation"] == "temperature"
                and self.core.states.get(ident, {}).get("mode") == "heat_cool"
            ):
                raise Invalid("both range targets required")
        if not self.core.available(ident):
            raise Invalid("device unavailable")
        operation, value = validated["operation"], validated["value"]
        kind, wire_field = "shared", "target_temperature"
        extras = {}
        if advanced is not None:
            kind, wire_field, value, extras = advanced
        elif operation == "mode":
            wire_field = MODE_FIELD
            if value == "heat_cool":
                value = "range"
        elif operation == "temperature_range":
            wire_field = "target_temperature_low"
            extras = {"target_temperature_high": value["high"]}
            value = value["low"]
        elif operation == "fan":
            kind, wire_field = "device", "fan_timer_timeout"
            value = 0 if value == "auto" else integer(int(self.clock()) + 600)
        key = self.home_key(ident) if kind == "structure" else f"{kind}.{ident}"
        records = self._records_for(ident)
        previous = records.get(key)
        desired = {wire_field: value, **extras}
        if previous is None or not desired.keys() <= previous.fingerprints.keys():
            raise Invalid("native control baseline unavailable")
        # A revision supersedes the bucket's earlier intent batch. Retain other
        # still-live intents with the same new revision so disjoint operations
        # are delivered together instead of overwriting one another.
        revision = integer(previous.revision + 1)
        timestamp = integer(max(int(self.clock() * 1000), previous.timestamp + 1))
        previous.revision, previous.timestamp = revision, timestamp
        for name, data in desired.items():
            previous.fingerprints[name] = hmac.digest(
                self._key,
                json.dumps(
                    canonical(data), sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode(),
                hashlib.sha256,
            )
        intents = self.intents.setdefault(ident, {})
        for op, pending in list(intents.items()):
            incompatible = operation == "mode" and (
                (value == "range" and op == "temperature")
                or (value != "range" and op == "temperature_range")
                or (value == "off" and op == "temperature")
            )
            if incompatible or (
                pending.key == key and pending.desired().keys() & desired.keys() and op != operation
            ):
                del intents[op]
                self.outcomes.setdefault(ident, {})[op] = "superseded"
        for pending in intents.values():
            if pending.key == key:
                pending.revision = revision
        item = Intent(
            uuid.uuid4().hex,
            key,
            wire_field,
            value,
            revision,
            self.core.clock() + 30,
            extra_values=extras,
        )
        intents[operation] = item
        self.outcomes.setdefault(ident, {})[operation] = "pending"
        self.notify(ident)
        return {**validated, "id": item.ident, "status": "pending"}

    def _values(self, ident, response):
        self._expire(ident)
        for row in response["objects"]:
            values = {
                name: data
                for i in self.intents.get(ident, {}).values()
                if i.key == row["object_key"] and i.revision == row["object_revision"]
                for name, data in i.desired().items()
            }
            if values:
                row["value"] = values
                for item in self.intents[ident].values():
                    if item.key == row["object_key"] and item.revision == row["object_revision"]:
                        item.sent = True
        return response

    def updates(self, ident, body):
        objects = self.normalize(ident, body, subscription=True)
        records = self._records_for(ident)
        replies = []
        for key, _, _, _, revision, timestamp in objects:
            previous = records.get(key)
            if previous is not None and (
                previous.revision != revision or previous.timestamp != timestamp
            ):
                replies.append(previous.metadata(key))
        return self._local_user_response(ident, body, self._values(ident, {"objects": replies}))

    def apply(self, ident, body, *, subscription=False):
        objects = self.normalize(ident, body, subscription=subscription)
        records = self._records_for(ident)
        accepted = {
            key
            for key, _, value, conditional, _, _ in objects
            if value is not None
            and (conditional is None or conditional == getattr(records.get(key), "revision", 0))
        }
        previous_home = self.home_key(ident)
        response = super().apply(ident, body, subscription=subscription)
        for key, kind, value, _, _, _ in objects:
            if key not in accepted or kind != "device" or not value or "structure_id" not in value:
                continue
            try:
                next_home = native_features.structure_key(value["structure_id"])
            except Invalid:
                next_home = None
            if previous_home != next_home:
                self.reported.get(ident, {}).pop("structure", None)
                self._records_for(ident).pop(previous_home, None)
                if self.intents.get(ident, {}).get("eco") is not None:
                    self.intents[ident].pop("eco")
                    self.outcomes.setdefault(ident, {})["eco"] = "superseded_by_device"
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
            if mode == "range":
                mode = "heat_cool"
            elif mode == "emergency":
                mode = "heat"
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
            reported_state.capture(self, ident, key, kind, value)
            for op, item in list(self.intents.get(ident, {}).items()):
                expected = item.desired()
                touched = expected.keys() & value.keys()
                if item.key != key or not touched:
                    continue
                if any(canonical(value[name]) != canonical(expected[name]) for name in touched):
                    outcome = "superseded_by_device"
                else:
                    observed = self.reported.get(ident, {}).get(kind, {}).get("values", {})
                    if not all(
                        name in observed and canonical(observed[name]) == canonical(want)
                        for name, want in expected.items()
                    ):
                        continue
                    outcome = "confirmed"
                self.outcomes.setdefault(ident, {})[op] = outcome
                del self.intents[ident][op]
            # A native telemetry delta may advance this bucket while an unrelated
            # intent waits. Keep its value attached to the current revision,
            # without extending the original deadline or changing reported state.
            for item in self.intents.get(ident, {}).values():
                if item.key == key:
                    item.revision = self._records_for(ident)[key].revision
        self.note_request(ident, "subscribe" if subscription else "put")
        self.notify(ident)
        # PUT is an acknowledgement of the device's own dirty fields. Adding
        # control values here can overwrite local changes and clear dirty flags.
        # Desired values travel only through the subscription response.
        return (
            self._local_user_response(ident, body, self._values(ident, response))
            if subscription
            else response
        )
