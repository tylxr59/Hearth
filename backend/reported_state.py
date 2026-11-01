"""Reported-only restart state. No pending intent, command replay or freshness."""

import hashlib
import hmac
import json

from backend.native import MAPPINGS, Bucket, canonical
from backend.reported_cache import FIELDS, FORMAT, reported_value, validate
from backend.validation import Invalid, state


def capture(native, ident, key, kind, value):
    if kind not in FIELDS:
        return
    records = native._records_for(ident)
    if key not in records:
        return
    saved = native.reported.setdefault(ident, {})
    item = saved.setdefault(kind, {"revision": 0, "timestamp": 0, "values": {}})
    for name, data in value.items():
        if name not in FIELDS[kind]:
            continue
        try:
            item["values"][name] = reported_value(name, data)
            native.restored_fields.get(ident, set()).discard((kind, name))
        except Invalid:
            item["values"].pop(name, None)
    item["revision"] = records[key].revision
    item["timestamp"] = records[key].timestamp
    native.reported_changed(ident)


def snapshot(native, saved_at):
    devices = {}
    for ident, records in native.reported.items():
        enrolled = native.core.registry.data["devices"].get(ident)
        if enrolled and native._generation.get(ident) == enrolled["hash"]:
            devices[ident] = {"generation": enrolled["hash"], "records": records}
    # validate returns a detached, bounded copy; caller may save off-thread.
    return validate({"format": FORMAT, "saved_at": saved_at, "devices": devices})


def restore(native, data):
    data = validate(data)
    if native._records or native.core.states or native.core.seen or native.intents:
        raise Invalid("reported state may load only before native traffic")
    restored = 0
    for ident, entry in data["devices"].items():
        enrolled = native.core.registry.data["devices"].get(ident)
        if not enrolled or enrolled["hash"] != entry["generation"]:
            continue
        caps = native.core.caps(ident)
        records = {}
        projection = {}
        features = {}
        for kind in ("device", "shared"):
            if kind not in entry["records"]:
                continue
            item = entry["records"][kind]
            values = item["values"]
            fingerprints = {}
            for name, value in values.items():
                fingerprints[name] = hmac.digest(
                    native._key,
                    json.dumps(
                        canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode(),
                    hashlib.sha256,
                )
            telemetry = {
                target: values[name]
                for name, target in MAPPINGS.get(kind, {}).items()
                if name in values
            }
            if telemetry:
                telemetry = state(telemetry, caps)
            projection.update(telemetry)
            for name, value in values.items():
                if type(value) is bool:
                    features[name] = value
            mode = values.get("target_temperature_type")
            if mode == "range":
                mode = "heat_cool"
            elif mode == "emergency":
                mode = "heat"
            if kind == "shared" and mode in caps["modes"]:
                projection["mode"] = mode
            if kind == "device" and caps["fan"] and "fan_timer_timeout" in values:
                projection["fan"] = "on" if values["fan_timer_timeout"] > native.clock() else "auto"
            records[f"{kind}.{ident}"] = Bucket(
                item["revision"], item["timestamp"], fingerprints, telemetry
            )
        if projection:
            native.core.states[ident] = state(projection, caps)
        native._records[ident] = records
        native._generation[ident] = enrolled["hash"]
        native.features[ident] = features
        native.reported[ident] = entry["records"]
        native.restored_fields[ident] = {
            (kind, name) for kind, item in entry["records"].items() for name in item["values"]
        }
        restored += 1
    # No core.report/touch, seen timestamps, intent restoration or notification.
    return restored
