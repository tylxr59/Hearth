"""Opt-in telemetry lab for the pinned NLE wire contract; no command delivery.

Protocol observations: docs/research/upstreams.json, NLE backend MIT reference.
Original implementation. Raw native values are never persisted or echoed; only
allowlisted telemetry and keyed, process-local field fingerprints are retained.
"""

import hashlib
import hmac
import json
import math
import re
import secrets
import time
from dataclasses import dataclass, field

from backend.validation import Invalid, state

MAX_BODY = 65536
MAX_OBJECTS = 32
MAX_FIELDS = 256
MAX_INTEGER = (1 << 53) - 1
BUCKETS = {
    "device",
    "shared",
    "schedule",
    "custom_schedule",
    "diagnostics",
    "device_alert_dialog",
    "diamond_sensor_config",
    "diamond_sensor_event",
    "rcs_settings",
    "cloud_algo",
    "occupancy",
}
UNBOUND_BUCKETS = {"user", "structure", "where", "link"}
META = {
    "object_key",
    "object_revision",
    "object_timestamp",
    "base_object_revision",
    "if_object_revision",
}
REJECTION_REASONS = {
    "invalid native revision or timestamp": "revision_or_timestamp",
    "native value nesting limit exceeded": "value_depth",
    "nonfinite native value": "nonfinite_value",
    "native object key required": "object_key",
    "native bucket ownership or type rejected": "bucket_owner_or_type",
    "native object envelope required": "envelope_type",
    "invalid native session": "session",
    "invalid native chunked flag": "chunked_flag",
    "ambiguous native object envelope": "envelope_shape",
    "native named bucket identity mismatch": "named_bucket_identity",
    "native named subscription identity mismatch": "named_subscription_identity",
    "invalid native object count": "object_count",
    "invalid native bucket": "bucket_shape",
    "duplicate native bucket": "duplicate_bucket",
    "bounded native value required": "value_shape_or_size",
    "native PUT value required": "put_value_missing",
    "inline native bootstrap value requires zero revision and timestamp": "bootstrap_metadata",
    "invalid native field name": "field_name",
    "invalid native field value": "field_value",
    "native bucket field limit exceeded": "field_count",
    "duplicate JSON key": "duplicate_json_key",
    "invalid JSON": "invalid_json",
    "number outside allowed range": "telemetry_range",
    "unsupported state field": "telemetry_field",
    "invalid firmware version": "firmware_value",
}
MAPPINGS = {
    "device": {
        "current_temperature": "temperature",
        "current_humidity": "humidity",
        "software_version": "firmware",
    },
    "shared": {"current_temperature": "temperature", "target_temperature": "target_temperature"},
}


class BucketShapeError(Invalid):
    """Fixed-field/type evidence only; never retains a bucket or its values."""

    def __init__(self, obj, subscription, detail):
        super().__init__("invalid native bucket")
        known = META | {"value", "filters"}
        fields = obj if isinstance(obj, dict) else {}
        filters = fields.get("filters")
        key = fields.get("object_key")
        kind = key.partition(".")[0] if isinstance(key, str) else None
        self.observation = {
            "known_bucket_kind": kind if kind in BUCKETS | UNBOUND_BUCKETS else "unknown",
            "detail": detail,
            "subscription": subscription,
            "bucket_type": json_type(obj),
            "known_member_types": {
                key: json_type(fields[key]) for key in sorted(known & fields.keys())
            },
            "unknown_member_count": min(len(fields.keys() - known), 257),
            "filter_count": min(len(filters), 257) if isinstance(filters, list) else None,
            "filter_item_types": sorted({json_type(item) for item in filters})
            if isinstance(filters, list)
            else [],
        }


def json_type(value):
    if value is None:
        return "null"
    return {
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
        list: "array",
        dict: "object",
    }.get(type(value), "other")


def has_empty_filters(body):
    if not isinstance(body, dict):
        return False
    objects = body.get("objects")
    if objects is None:
        objects = [value for key, value in body.items() if key not in ("session", "chunked")]
    return isinstance(objects, list) and any(
        isinstance(obj, dict) and obj.get("filters") == [] for obj in objects
    )


def integer(value):
    if type(value) is not int or not 0 <= value <= MAX_INTEGER:
        raise Invalid("invalid native revision or timestamp")
    return value


def canonical(value, depth=0):
    if depth > 16:
        raise Invalid("native value nesting limit exceeded")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Invalid("nonfinite native value")
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {k: canonical(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v, depth + 1) for v in value]
    return value


def object_key(value, ident):
    if not isinstance(value, str):
        raise Invalid("native object key required")
    kind, dot, owner = value.partition(".")
    if dot and kind in UNBOUND_BUCKETS and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner):
        return kind
    if not dot or kind not in BUCKETS or owner != ident:
        raise Invalid("native bucket ownership or type rejected")
    return kind


def envelope(ident, body, *, subscription=False, structure_key=None):
    """Normalize only the two pinned NLE shapes; never infer device identity."""
    if not isinstance(body, dict):
        raise Invalid("native object envelope required")
    session = body.get("session", "")
    if not isinstance(session, str) or not re.fullmatch(r"[\x20-\x7e]{0,256}", session):
        raise Invalid("invalid native session")
    options = {"session", "chunked"} if subscription else {"session"}
    if subscription and type(body.get("chunked", False)) is not bool:
        raise Invalid("invalid native chunked flag")
    if "objects" in body:
        if set(body) - (options | {"objects"}) or not isinstance(body["objects"], list):
            raise Invalid("ambiguous native object envelope")
        objects = body["objects"]
    else:
        objects = []
        for outer, obj in body.items():
            if outer in options:
                continue
            if not isinstance(obj, dict):
                raise Invalid("native named bucket identity mismatch")
            if subscription:
                if object_key(obj.get("object_key"), ident) != outer:
                    raise Invalid("native named subscription identity mismatch")
                objects.append(obj)
            else:
                if obj.get("object_key") != outer or "value" in obj:
                    raise Invalid("native named bucket identity mismatch")
                objects.append(
                    {k: v for k, v in obj.items() if k in META}
                    | {"value": {k: v for k, v in obj.items() if k not in META}}
                )
    if not 1 <= len(objects) <= MAX_OBJECTS:
        raise Invalid("invalid native object count")
    normalized, seen = [], set()
    for obj in objects:
        allowed = META | {"value"} | ({"filters"} if subscription else set())
        if not isinstance(obj, dict):
            raise BucketShapeError(obj, subscription, "not_object")
        if "object_key" not in obj:
            raise BucketShapeError(obj, subscription, "missing_object_key")
        if set(obj) - allowed:
            raise BucketShapeError(obj, subscription, "unexpected_members")
        if "filters" in obj and obj["filters"] != []:
            raise BucketShapeError(obj, subscription, "nonempty_or_invalid_filters")
        key = obj["object_key"]
        kind = object_key(key, ident)
        if key in seen:
            raise Invalid("duplicate native bucket")
        seen.add(key)
        for name in META - {"object_key"}:
            if name in obj and obj[name] is not None:
                integer(obj[name])
        value = obj.get("value")
        if kind in UNBOUND_BUCKETS and key != structure_key:
            # Account ownership cannot be learned from this request. Leave its
            # bucket unacknowledged; do not retain or reflect an account value.
            if value is not None:
                if not isinstance(value, dict) or len(value) > MAX_FIELDS:
                    raise Invalid("bounded native value required")
                canonical(value)
            continue
        if value is None:
            if not subscription:
                raise Invalid("native PUT value required")
        elif not isinstance(value, dict) or len(value) > MAX_FIELDS:
            raise Invalid("bounded native value required")
        if (
            subscription
            and value is not None
            and (
                obj.get("object_revision", 0) not in (0, None)
                or obj.get("object_timestamp", 0) not in (0, None)
            )
        ):
            raise Invalid("inline native bootstrap value requires zero revision and timestamp")
        normalized.append(
            (
                key,
                kind,
                value,
                obj.get("if_object_revision"),
                obj.get("object_revision") or 0,
                obj.get("object_timestamp") or 0,
            )
        )
    return normalized


@dataclass
class Bucket:
    revision: int = 0
    timestamp: int = 0
    fingerprints: dict = field(default_factory=dict)
    telemetry: dict = field(default_factory=dict)

    def metadata(self, key):
        # Native parser consumes revision/time before key. No value echo.
        return {
            "object_revision": self.revision,
            "object_timestamp": self.timestamp,
            "object_key": key,
        }


class NativeTelemetry:
    def __init__(self, core, clock=time.time):
        self.core, self.clock = core, clock
        self._key = secrets.token_bytes(32)
        self._records, self._generation = {}, {}
        self._rejections, self._last_rejection = {}, None
        self._last_bucket_shape = None
        self._empty_filters_accepted = False

    def reject(self, error):
        # Finite vocabulary only: never retain exception text, payload fields,
        # credentials, identifiers, addresses or per-request data.
        reason = REJECTION_REASONS.get(str(error), "other")
        self._rejections[reason] = min(self._rejections.get(reason, 0) + 1, 2147483647)
        self._last_rejection = reason
        if isinstance(error, BucketShapeError):
            self._last_bucket_shape = error.observation

    def diagnostics(self):
        result = {"rejections": dict(self._rejections), "last_rejection": self._last_rejection}
        if self._last_bucket_shape is not None:
            result["last_bucket_shape"] = json.loads(json.dumps(self._last_bucket_shape))
        if self._empty_filters_accepted:
            result["empty_subscription_filters_accepted"] = True
        return result

    def _records_for(self, ident):
        generation = self.core.registry.data["devices"][ident]["hash"]
        if self._generation.get(ident) != generation:
            self._records.pop(ident, None)
            self._generation[ident] = generation
        return self._records.get(ident, {})

    def normalize(self, ident, body, *, subscription=False):
        result = envelope(ident, body, subscription=subscription)
        self._empty_filters_accepted |= subscription and has_empty_filters(body)
        return result

    def apply(self, ident, body, *, subscription=False):
        objects = self.normalize(ident, body, subscription=subscription)
        caps = self.core.caps(ident)
        prepared = []
        # Validate every projection and fingerprint before any state mutation.
        for key, kind, value, conditional, client_revision, client_timestamp in objects:
            fingerprints, projection = {}, {}
            if value is not None:
                for name, data in value.items():
                    if not isinstance(name, str) or not re.fullmatch(
                        r"[A-Za-z0-9_.:-]{1,96}", name
                    ):
                        raise Invalid("invalid native field name")
                    try:
                        encoded = json.dumps(
                            canonical(data), sort_keys=True, separators=(",", ":"), allow_nan=False
                        ).encode()
                    except (ValueError, TypeError, RecursionError) as exc:
                        raise Invalid("invalid native field value") from exc
                    fingerprints[name] = hmac.digest(self._key, encoded, hashlib.sha256)
                    if name in MAPPINGS.get(kind, {}):
                        projection[MAPPINGS[kind][name]] = data
                if projection:
                    projection = state(projection, caps)
            prepared.append(
                (
                    key,
                    value,
                    conditional,
                    fingerprints,
                    projection,
                    client_revision,
                    client_timestamp,
                )
            )
        current = self._records_for(ident)
        planned = dict(current)
        replies, accepted_telemetry = [], False
        timestamp = integer(int(self.clock() * 1000))
        for (
            key,
            value,
            conditional,
            fingerprints,
            projection,
            client_revision,
            client_timestamp,
        ) in prepared:
            previous = planned.get(key, Bucket())
            if value is None:
                if previous.revision != client_revision or previous.timestamp != client_timestamp:
                    replies.append(previous.metadata(key))
                continue
            if conditional is not None and conditional != previous.revision:
                replies.append(previous.metadata(key))
                continue
            merged = previous.fingerprints | fingerprints
            if len(merged) > MAX_FIELDS:
                raise Invalid("native bucket field limit exceeded")
            changed = merged != previous.fingerprints
            revision = integer(previous.revision + int(changed))
            updated_at = (
                integer(max(timestamp, previous.timestamp + 1)) if changed else previous.timestamp
            )
            updated = Bucket(revision, updated_at, merged, previous.telemetry | projection)
            planned[key] = updated
            replies.append(updated.metadata(key))
            accepted_telemetry |= bool(projection)
        if accepted_telemetry:
            # Shared current_temperature is authoritative, including zero.
            merged_telemetry = {}
            for kind in ("device", "shared"):
                bucket = planned.get(f"{kind}.{ident}")
                if bucket:
                    merged_telemetry.update(bucket.telemetry)
            self.core.report(ident, merged_telemetry)
        self._records[ident] = planned
        return {"objects": replies}

    def listing(self, ident):
        return {"objects": [value.metadata(key) for key, value in self._records_for(ident).items()]}
