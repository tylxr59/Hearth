"""Opt-in native setpoint/mode/fan intents; native firmware owns all HVAC loops.

Only allowlisted control scalars are retained. Responses carry partial values,
never raw bucket echoes. Delivery is not confirmation; only accepted native PUT
values update reported state. Control intents are never persisted or replayed.
Reported-state caching and explicit local user/home configuration are separate.
"""

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field

from backend import native_features, native_pairing, reported_state
from backend.native import NativeTelemetry, canonical, envelope, has_empty_filters, integer
from backend.schedule_state import ScheduleState
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
    stream_write_completed: bool = False
    notification_sent: bool = False
    notification_acknowledged: bool = False
    metadata_acknowledged: bool = False
    written_metadata: tuple | None = None
    confirmation_source: str | None = None
    extra_values: dict = field(default_factory=dict)
    observed_fields: set = field(default_factory=set)

    def desired(self):
        return {self.field: self.value, **self.extra_values}


class NativeControls(NativeTelemetry):
    def __init__(self, core, clock=time.time):
        super().__init__(core, clock)
        self.intents = {}
        self.features = {}
        self.outcomes = {}
        self.receipts = {}
        self.acknowledged_targets = {}
        self.reported = {}
        self.restored_fields = {}
        self.reported_changed = lambda _ident: None
        self.schedules = ScheduleState(self)
        self.requests = {}
        self.last_request = {}
        self.notify = lambda _ident: None
        self._local_users = {}
        self._local_user_offered = set()
        self._local_user_acknowledged = set()
        self._local_home_offered = set()
        self._local_home_acknowledged = set()
        self._schedule_shapes = {}

    def _records_for(self, ident):
        self.core.caps(ident)
        generation = self.core.registry.data["devices"][ident]["hash"]
        if self._generation.get(ident) != generation:
            self.intents.pop(ident, None)
            self.features.pop(ident, None)
            self.outcomes.pop(ident, None)
            self.receipts.pop(ident, None)
            self.acknowledged_targets.pop(ident, None)
            self.schedules.forget(ident)
            self.reported.pop(ident, None)
            self.restored_fields.pop(ident, None)
            self.requests.pop(ident, None)
            self.last_request.pop(ident, None)
            self._local_users.pop(ident, None)
            self._local_user_offered.discard(ident)
            self._local_user_acknowledged.discard(ident)
            self._local_home_offered.discard(ident)
            self._local_home_acknowledged.discard(ident)
            self._schedule_shapes.pop(ident, None)
        return super()._records_for(ident)

    def home_key(self, ident):
        value = self.reported.get(ident, {}).get("device", {}).get("values", {}).get("structure_id")
        if value is not None:
            return native_features.structure_key(value)
        return self.reported.get(ident, {}).get("structure", {}).get("key")

    def normalize(self, ident, body, *, subscription=False):
        # A home bucket is scoped to this authenticated device's record namespace.
        # Use its accepted device reference or its explicit enrollment-bound
        # configuration; never infer ownership from an arbitrary structure upload.
        self._records_for(ident)
        home = self.transport_home_key(ident)
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
            previous = self._local_users.get(ident)
            self._local_users[ident] = dict(record)
            if previous is None or native_pairing.metadata(previous) != native_pairing.metadata(
                record
            ):
                self._local_user_offered.discard(ident)
                self._local_user_acknowledged.discard(ident)
            if previous is None or previous.get("home") != record.get("home"):
                self._local_home_offered.discard(ident)
                self._local_home_acknowledged.discard(ident)
            self.notify(ident)

    def local_user_view(self, ident):
        self._records_for(ident)
        return {
            "configured": ident in self._local_users,
            "offered": ident in self._local_user_offered,
            "metadata_acknowledged": ident in self._local_user_acknowledged,
        }

    def transport_home_key(self, ident):
        # Configured routing scope is not a device-reported home baseline.
        observed = self.home_key(ident)
        record = self._local_users.get(ident)
        return observed or (
            native_pairing.home_metadata(record)["object_key"]
            if record is not None and "home" in record
            else None
        )

    def local_home_view(self, ident):
        self._records_for(ident)
        record = self._local_users.get(ident)
        configured = record is not None and "home" in record
        key = native_pairing.home_metadata(record)["object_key"] if configured else None
        observed = self.home_key(ident)
        device_reference = (
            self.reported.get(ident, {}).get("device", {}).get("values", {}).get("structure_id")
        )
        return {
            "configured": configured,
            "offered": ident in self._local_home_offered,
            "metadata_acknowledged": ident in self._local_home_acknowledged,
            "device_reference_observed": configured
            and device_reference is not None
            and native_features.structure_key(device_reference) == key,
            "structure_identity_observed": configured
            and self.reported.get(ident, {}).get("structure", {}).get("key") == key,
            "conflict": configured and observed is not None and observed != key,
        }

    def _local_user_response(self, ident, body, response):
        record = self._local_users.get(ident)
        if record is None:
            return response
        rows = envelope(
            ident,
            body,
            subscription=True,
            structure_key=self.transport_home_key(ident),
            user_key=native_pairing.metadata(record)["object_key"],
        )
        announcements = []
        configurations = [
            (
                native_pairing.metadata(record),
                native_pairing.announcement(record),
                self._local_user_offered,
                self._local_user_acknowledged,
            )
        ]
        if "home" in record and not self.local_home_view(ident)["conflict"]:
            configurations.append(
                (
                    native_pairing.home_metadata(record),
                    native_pairing.home_announcement(record),
                    self._local_home_offered,
                    self._local_home_acknowledged,
                )
            )
        for meta, announcement, offered, acknowledged in configurations:
            own = next((row for row in rows if row[0] == meta["object_key"]), None)
            matches = own is not None and own[4:] == (
                meta["object_revision"],
                meta["object_timestamp"],
            )
            if offered is self._local_home_offered and ident in offered:
                current = self._records_for(ident).get(meta["object_key"])
                matches |= (
                    own is not None
                    and current is not None
                    and bool(current.fingerprints)
                    and own[4:] == (current.revision, current.timestamp)
                )
            if matches:
                acknowledged.add(ident)
            if ident not in offered or (
                offered is self._local_user_offered and own is not None and not matches
            ):
                offered.add(ident)
                announcements.append(announcement)
        # User precedes home; never claim configuration as observed telemetry.
        keys = {row["object_key"] for row in announcements}
        return {
            "objects": announcements
            + [row for row in response["objects"] if row["object_key"] not in keys]
        }

    def bootstrap_listing(self, ident):
        response = self.listing(ident)
        record = self._local_users.get(ident)
        if record is not None:
            configurations = [
                (
                    native_pairing.announcement(record),
                    self._local_user_offered,
                    self._local_user_acknowledged,
                )
            ]
            if "home" in record and not self.local_home_view(ident)["conflict"]:
                configurations.append(
                    (
                        native_pairing.home_announcement(record),
                        self._local_home_offered,
                        self._local_home_acknowledged,
                    )
                )
            keys = {row["object_key"] for row, _, _ in configurations}
            response["objects"] = [row for row, _, _ in configurations] + [
                row for row in response["objects"] if row["object_key"] not in keys
            ]
            for _, offered, acknowledged in configurations:
                offered.add(ident)
                acknowledged.discard(ident)
        return response

    def listing(self, ident):
        response = super().listing(ident)
        record = self._local_users.get(ident)
        if record is not None:
            metadata = [native_pairing.metadata(record)]
            if "home" in record and not self.local_home_view(ident)["conflict"]:
                home = native_pairing.home_metadata(record)
                if not any(row["object_key"] == home["object_key"] for row in response["objects"]):
                    metadata.append(home)
            keys = {row["object_key"] for row in metadata}
            response["objects"] = metadata + [
                row for row in response["objects"] if row["object_key"] not in keys
            ]
        return response

    def snapshot_reported(self):
        return reported_state.snapshot(self, integer(int(self.clock() * 1000)))

    def restore_reported(self, data):
        return reported_state.restore(self, data)

    def eco_mode(self, ident):
        records = self._records_for(ident)
        observed = self.reported.get(ident, {}).get("device", {}).get("values", {}).get("eco")
        if isinstance(observed, dict):
            return observed["mode"]
        bucket = records.get(f"device.{ident}")
        return "unknown" if bucket is not None and "eco" in bucket.fingerprints else None

    def state_source(self, ident, field):
        self._records_for(ident)
        if field in self.acknowledged_targets.get(ident, {}):
            return "acknowledged"
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
            "preset": ("device", "eco")
            if self.eco_mode(ident) is not None
            else ("structure", "manual_eco_all"),
        }.get(field)
        if source is None or source[1] not in records.get(source[0], {}).get("values", {}):
            return "unknown"
        return "cache" if source in self.restored_fields.get(ident, set()) else "device"

    def target_value(self, ident, field="target_temperature"):
        self._records_for(ident)
        assigned = self.acknowledged_targets.get(ident, {})
        if field in assigned:
            return assigned[field]
        if field == "target_temperature":
            return self.core.states.get(ident, {}).get(field)
        return self.reported.get(ident, {}).get("shared", {}).get("values", {}).get(field)

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
        try:
            schedule_view = self.schedules.view(ident)
        except Invalid:
            schedule_view = None
        return {
            "capabilities": self.capabilities(ident),
            "command_status": self.command_status(ident),
            "delivery_receipts": {
                op: dict(receipt) for op, receipt in self.receipts.get(ident, {}).items()
            },
            "pending": {
                op: {
                    "offered": i.sent,
                    "stream_write_completed": i.stream_write_completed,
                    "notification_acknowledged": i.notification_acknowledged,
                    "metadata_acknowledged": i.metadata_acknowledged,
                    "seconds_remaining": max(0, round(i.expires - self.core.clock(), 1)),
                }
                for op, i in self.intents.get(ident, {}).items()
            },
            "requests": dict(self.requests.get(ident, {})),
            "last_request_age": max(0, round(self.core.clock() - self.last_request[ident], 1))
            if ident in self.last_request
            else None,
            "feature_baselines": {
                "home_reference_observed": (
                    device is not None and "structure_id" in device.fingerprints
                )
                or bool(self.reported.get(ident, {}).get("structure", {}).get("key")),
                "home_reference_source": "device"
                if self.reported.get(ident, {})
                .get("device", {})
                .get("values", {})
                .get("structure_id")
                is not None
                else "structure"
                if self.reported.get(ident, {}).get("structure", {}).get("key")
                else None,
                "home_reference_validated": self.home_key(ident) is not None,
                "native_eco_field_observed": device is not None and "eco" in device.fingerprints,
                "schedule_bucket_observed": f"schedule.{ident}" in records,
                "schedule_shape": self._schedule_shapes.get(ident),
                "schedule_schema_validated": schedule_view is not None,
                "schedule_state_source": schedule_view["source"] if schedule_view else "unknown",
                "schedule_fresh": schedule_view is not None
                and schedule_view["source"] in ("device", "acknowledged"),
                "observed_bucket_kinds": sorted({key.partition(".")[0] for key in records}),
            },
            "local_pairing": self.local_user_view(ident),
            "local_home": self.local_home_view(ident),
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

    def _finish(self, ident, op, item, outcome):
        if outcome in ("superseded", "superseded_by_device"):
            assigned = self.acknowledged_targets.get(ident, {})
            for name in item.desired():
                assigned.pop(name, None)
        self.receipts.setdefault(ident, {})[op] = {
            "outcome": outcome,
            "offered": item.sent,
            "stream_write_completed": item.stream_write_completed,
            "notification_acknowledged": item.notification_acknowledged,
            "metadata_acknowledged": item.metadata_acknowledged,
            "matching_reported_field_count": len(item.observed_fields),
            "required_field_count": 1
            if item.confirmation_source == "device_eco_mode"
            else len(item.desired()),
        }
        if item.confirmation_source:
            self.receipts[ident][op]["confirmation_source"] = item.confirmation_source
        if op == "schedule":
            self.schedules.finished(ident, item, outcome)
        self.outcomes.setdefault(ident, {})[op] = outcome
        self.intents.get(ident, {}).pop(op, None)

    def note_stream_write(self, ident, response):
        self._records_for(ident)
        for row in response["objects"]:
            for item in self.intents.get(ident, {}).values():
                if (
                    item.key == row["object_key"]
                    and item.revision == row["object_revision"]
                    and isinstance(row.get("value"), dict)
                    and all(
                        name in row["value"] and canonical(row["value"][name]) == canonical(value)
                        for name, value in item.desired().items()
                    )
                ):
                    item.stream_write_completed = True
                    item.written_metadata = (row["object_revision"], row["object_timestamp"])
                    if row["value"].get("target_change_pending") is True and item.field in (
                        "target_temperature",
                        "target_temperature_low",
                    ):
                        item.notification_sent = True

    def _expire(self, ident):
        now = self.core.clock()
        for op, item in list(self.intents.get(ident, {}).items()):
            if item.expires <= now:
                self._finish(
                    ident,
                    op,
                    item,
                    "acknowledged"
                    if item.notification_acknowledged or item.metadata_acknowledged
                    else "expired",
                )

    def command_status(self, ident):
        self._records_for(ident)
        self._expire(ident)
        result = dict(self.outcomes.get(ident, {}))
        for op, item in self.intents.get(ident, {}).items():
            if item.notification_acknowledged or item.metadata_acknowledged:
                result[op] = "acknowledged"
        return result

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
        baseline = self.schedules.view(ident)
        if baseline["revision"] != record.revision or baseline["source"] not in (
            "device",
            "acknowledged",
        ):
            raise Invalid("a fresh native weekly schedule report is required before replacement")
        if not schedule_backed_up:
            raise Invalid("use the HA schedule action to preserve the current week first")
        assignment = self.schedules.requested.get(ident) or self.schedules.committed.get(ident)
        wire_value = (
            assignment["value"] if assignment else self.reported[ident]["schedule"]["values"]
        )
        if "manual_schedule" in wire_value:
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
                self._finish(ident, op, pending, "superseded")
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
        if operation == "schedule":
            self.schedules.queued(ident, item, timestamp)
        self.receipts.get(ident, {}).pop(operation, None)
        self.outcomes.setdefault(ident, {})[operation] = "pending"
        self.notify(ident)
        return {**validated, "id": item.ident, "status": "pending"}

    def _values(self, ident, response, acknowledge_keys=()):
        self._expire(ident)
        rows = {row["object_key"]: dict(row) for row in response["objects"]}
        records = self._records_for(ident)
        # A PUT acknowledgement may advance the client's metadata without proving
        # it received a pending desired value. Until native values confirm it,
        # include that live intent even when the client claims matching metadata.
        for item in self.intents.get(ident, {}).values():
            if item.notification_acknowledged or item.metadata_acknowledged:
                continue
            record = records.get(item.key)
            if record is not None and record.revision == item.revision:
                rows.setdefault(item.key, record.metadata(item.key))
        for row in rows.values():
            values = {
                name: data
                for i in self.intents.get(ident, {}).values()
                if i.key == row["object_key"]
                and i.revision == row["object_revision"]
                and not i.notification_acknowledged
                and not i.metadata_acknowledged
                for name, data in i.desired().items()
            }
            if values:
                if row["object_key"] == f"shared.{ident}" and values.keys() & {
                    "target_temperature",
                    "target_temperature_low",
                    "target_temperature_high",
                }:
                    # Pinned NLE's transient display/report notification. It is
                    # delivery metadata, not a desired value to confirm or cache.
                    values["target_change_pending"] = True
                row["value"] = values
                for item in self.intents[ident].values():
                    if item.key == row["object_key"] and item.revision == row["object_revision"]:
                        item.sent = True
        # Unactionable stale metadata must not close a quiet long poll. Real
        # inline bootstrap values still receive their metadata acknowledgements.
        return {
            "objects": [
                row
                for row in rows.values()
                if "value" in row or row["object_key"] in acknowledge_keys
            ]
        }

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
        self._records_for(ident)
        self._expire(ident)
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
        if subscription:
            self.schedules.observe_metadata(ident, objects)
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
                    self._finish(ident, "eco", self.intents[ident]["eco"], "superseded_by_device")
        for key, kind, value, _, _, _ in objects:
            if key not in accepted or value is None:
                continue
            if kind in ("device", "shared"):
                observed = self.features.setdefault(ident, {})
                for name in FEATURES & value.keys():
                    observed[name] = value[name] if type(value[name]) is bool else None
            if kind == "shared":
                assigned = self.acknowledged_targets.get(ident, {})
                for name in assigned.keys() & value.keys():
                    assigned.pop(name)
                # This is a client acknowledgement of a written notification,
                # not an explicit target report or proof of equipment operation.
                if value.get("target_change_pending") is False:
                    for item in self.intents.get(ident, {}).values():
                        if (
                            item.key == key
                            and item.notification_sent
                            and not item.notification_acknowledged
                        ):
                            item.notification_acknowledged = True
                            self.acknowledged_targets.setdefault(ident, {}).update(
                                {
                                    name: target
                                    for name, target in item.desired().items()
                                    if name not in value and name not in item.observed_fields
                                }
                            )
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
            had_schedule_assignment = (
                self.schedules.native_report(ident) if kind == "schedule" else False
            )
            reported_state.capture(self, ident, key, kind, value)
            if kind == "schedule":
                self.schedules.capture_complete(ident, value)
            if had_schedule_assignment and not self.reported.get(ident, {}).get("schedule"):
                pending = self.intents.get(ident, {}).get("schedule")
                if pending:
                    self._finish(ident, "schedule", pending, "superseded_by_device")
            eco = self.intents.get(ident, {}).get("eco")
            mode = (
                value.get("eco", {}).get("mode")
                if kind == "device" and isinstance(value.get("eco"), dict)
                else None
            )
            if eco and mode in ("manual-eco", "schedule", "auto-eco"):
                matches = (eco.value is True) == (mode == "manual-eco")
                if matches or eco.stream_write_completed:
                    eco.confirmation_source = "device_eco_mode"
                    eco.observed_fields = {"device.eco.mode"} if matches else set()
                    self._finish(
                        ident, "eco", eco, "confirmed" if matches else "superseded_by_device"
                    )
            for op, item in list(self.intents.get(ident, {}).items()):
                expected = item.desired()
                touched = expected.keys() & value.keys()
                if item.key != key or not touched:
                    continue
                if any(canonical(value[name]) != canonical(expected[name]) for name in touched):
                    outcome = "superseded_by_device"
                else:
                    item.observed_fields.update(touched)
                    observed = self.reported.get(ident, {}).get(kind, {}).get("values", {})
                    if not expected.keys() <= item.observed_fields or not all(
                        name in observed and canonical(observed[name]) == canonical(want)
                        for name, want in expected.items()
                    ):
                        continue
                    outcome = "confirmed"
                self._finish(ident, op, item, outcome)
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
            self._local_user_response(
                ident,
                body,
                self._values(ident, response, {row[0] for row in objects if row[2] is not None}),
            )
            if subscription
            else response
        )
