"""Known acknowledged schedule configuration; never a durable command queue."""

import json

from .native import Bucket, canonical, integer
from .native_features import schedule_record, schedule_week
from .registry import token_valid
from .validation import Invalid, loads, serial

FORMAT = "hearth-known-schedules-v1"
NAME = "known-schedules.json"
LIMIT = 512 * 1024


def validate(data):
    if not isinstance(data, dict) or set(data) != {"format", "devices"} or data["format"] != FORMAT:
        raise Invalid("acknowledged schedule document required")
    if not isinstance(data["devices"], dict) or len(data["devices"]) > 64:
        raise Invalid("bounded acknowledged schedules required")
    result = {}
    for ident, item in data["devices"].items():
        serial(ident)
        if not isinstance(item, dict) or set(item) != {
            "generation",
            "revision",
            "timestamp",
            "value",
            "source",
        }:
            raise Invalid("acknowledged schedule record required")
        if (
            item["source"] not in ("device", "acknowledged")
            or not token_valid(item["generation"])
            or integer(item["revision"]) == 0
            or integer(item["timestamp"]) == 0
        ):
            raise Invalid("acknowledged schedule metadata required")
        result[ident] = {**item, "value": schedule_record(item["value"])}
    return {"format": FORMAT, "devices": result}


def encode(data):
    raw = json.dumps(
        validate(data), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(raw) > LIMIT:
        raise Invalid("acknowledged schedule document too large")
    return raw


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > LIMIT:
        raise Invalid("bounded acknowledged schedule bytes required")
    return validate(loads(raw))


class ScheduleState:
    def __init__(self, native):
        self.native = native
        self.committed = {}
        self.requested = {}

    def forget(self, ident):
        self.committed.pop(ident, None)
        self.requested.pop(ident, None)

    def queued(self, ident, item, timestamp):
        self.requested[ident] = {
            "value": schedule_record(item.desired()),
            "revision": item.revision,
            "timestamp": timestamp,
            "state": "pending",
            "intent": item.ident,
        }

    def finished(self, ident, item, outcome):
        entry = self.requested.get(ident)
        if entry and entry["intent"] == item.ident:
            if outcome == "expired":
                entry["state"] = "unconfirmed"
            else:
                self.requested.pop(ident, None)

    def native_report(self, ident):
        had_assignment = ident in self.requested or ident in self.committed
        self.forget(ident)
        # A partial native delta cannot safely be merged into an older report
        # after a cloud replacement. Require a complete validated native week.
        if had_assignment:
            self.native.reported.get(ident, {}).pop("schedule", None)
        return had_assignment

    def capture_complete(self, ident, value):
        try:
            schedule_record(value)
        except Invalid:
            return
        report = self.native.reported.get(ident, {}).get("schedule")
        if report:
            self.committed[ident] = {
                "value": schedule_record(report["values"]),
                "revision": report["revision"],
                "timestamp": report["timestamp"],
                "fresh": True,
                "source": "device",
            }

    def observe_metadata(self, ident, rows):
        for key, kind, value, _, revision, timestamp in rows:
            if kind != "schedule" or value is not None:
                continue
            item = self.native.intents.get(ident, {}).get("schedule")
            request = self.requested.get(ident)
            if (
                item is not None
                and request is not None
                and request["intent"] == item.ident
                and item.stream_write_completed
                and item.written_metadata == (revision, timestamp)
            ):
                item.metadata_acknowledged = True
                self.committed[ident] = {
                    "value": request["value"],
                    "revision": revision,
                    "timestamp": timestamp,
                    "fresh": True,
                    "source": "acknowledged",
                }
                self.requested.pop(ident)
                # Configuration acknowledgement completes delivery. A later
                # native week is authoritative, but is not needed to keep an
                # already acknowledged command out of the delivery queue.
                self.native._finish(ident, "schedule", item, "acknowledged")
                self.native.reported_changed(ident)
                continue
            entry = self.committed.get(ident)
            if (
                entry
                and (entry["revision"], entry["timestamp"]) == (revision, timestamp)
                and not entry["fresh"]
            ):
                entry["fresh"] = True
                entry["source"] = "acknowledged"
                self.native.reported_changed(ident)

    def view(self, ident):
        self.native._records_for(ident)
        pending = self.requested.get(ident)
        if pending:
            return {
                "schedule": schedule_week(pending["value"]),
                "revision": pending["revision"],
                "source": pending["state"],
            }
        entry = self.committed.get(ident)
        if entry:
            return {
                "schedule": schedule_week(entry["value"]),
                "revision": entry["revision"],
                "source": entry["source"] if entry["fresh"] else "cache",
            }
        report = self.native.reported.get(ident, {}).get("schedule")
        if report is None:
            raise Invalid("No validated weekly schedule available yet")
        restored = any(
            kind == "schedule" for kind, _ in self.native.restored_fields.get(ident, set())
        )
        return {
            "schedule": schedule_week(report["values"]),
            "revision": report["revision"],
            "source": "cache" if restored else "device",
        }

    def snapshot(self):
        devices = {}
        for ident, entry in self.committed.items():
            enrolled = self.native.core.registry.data["devices"].get(ident)
            if enrolled and self.native._generation.get(ident) == enrolled["hash"]:
                devices[ident] = {
                    "generation": enrolled["hash"],
                    "revision": entry["revision"],
                    "timestamp": entry["timestamp"],
                    "value": entry["value"],
                    "source": entry["source"],
                }
        return validate({"format": FORMAT, "devices": devices})

    def restore(self, data):
        if self.native.core.seen or self.native.intents or self.native.requests:
            raise Invalid("schedule configuration may load only before native traffic")
        import hashlib
        import hmac

        for ident, entry in validate(data)["devices"].items():
            enrolled = self.native.core.registry.data["devices"].get(ident)
            if not enrolled or enrolled["hash"] != entry["generation"]:
                continue
            records = self.native._records_for(ident)
            key = f"schedule.{ident}"
            previous = records.get(key)
            if previous is not None:
                if previous.timestamp > entry["timestamp"]:
                    continue
                if previous.timestamp == entry["timestamp"]:
                    report = self.native.reported.get(ident, {}).get("schedule")
                    if (
                        previous.revision != entry["revision"]
                        or report is None
                        or canonical(report["values"]) != canonical(entry["value"])
                    ):
                        continue
            fingerprints = {
                name: hmac.digest(
                    self.native._key,
                    json.dumps(
                        canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode(),
                    hashlib.sha256,
                )
                for name, value in entry["value"].items()
            }
            records[key] = Bucket(entry["revision"], entry["timestamp"], fingerprints, {})
            self.committed[ident] = {
                "value": entry["value"],
                "revision": entry["revision"],
                "timestamp": entry["timestamp"],
                "fresh": False,
                "source": entry["source"],
            }
