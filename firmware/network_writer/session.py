"""Strict four-file evidence ordering; never authorizes a device boot or commit."""

import hashlib
import json

from backend.validation import loads
from firmware.file_writer import protocol as p
from firmware.file_writer.session import Session
from firmware.network_probe.run import validate_payload


def selftest(payload, *, shared_originals=False):
    if shared_originals:
        raw = loads(payload)
        if (
            not isinstance(raw, dict)
            or type(raw.get("shared_transaction_cases")) is not int
            or raw.pop("shared_transaction_cases") != 20
        ):
            raise ValueError("all twenty shared-original RAM cases required")
        row = validate_payload(json.dumps(raw).encode())
        row["shared_transaction_cases"] = 20
    else:
        row = validate_payload(payload)
    expected = {
        "stream_cases": 41,
        "transaction_cases": 20,
        "child_status": 0,
        "child_output_bytes": 0,
        "real_files_checked": 0,
        "phase": 0,
        "real_preflight": False,
        "flash_writes": False,
        "diagnostic_hex": "",
    }
    if any(row[k] != v for k, v in expected.items()):
        raise ValueError("all61 synthetic checks required before real-file preflight")
    return row


def result(payload, action, *, target_count=4, preflight_only=False):
    if len(payload) > p.MAX_PAYLOAD or type(preflight_only) is not bool:
        raise ValueError("bounded result and explicit preflight-only mode required")
    raw = loads(payload)
    extra = {"memory_free", "space_available", "space_required", "preflight_only"}
    counters = {}
    if isinstance(raw, dict) and extra & raw.keys():
        if not extra <= raw.keys():
            raise ValueError("complete resource diagnostic fields required")
        counters = {key: raw.pop(key) for key in extra}
        if (
            any(type(v) is not int for v in counters.values())
            or not 0 <= counters["memory_free"] <= 1073741824
            or not 0 <= counters["space_available"] < 2**32
            or not 0 <= counters["space_required"] < 2**32
            or counters["preflight_only"] != int(preflight_only)
        ):
            raise ValueError("bounded matching resource diagnostic required")
    elif preflight_only:
        raise ValueError("explicit preflight-only result required")
    row = p.validate_result(json.dumps(raw).encode(), action, target_count=target_count)
    if preflight_only and (
        action != 1
        or any(
            row[k]
            for k in (
                "commit_received",
                "window_opened",
                "rw_attempted",
                "transaction_called",
                "program",
                "erase",
                "marker",
                "failed",
                "complete",
            )
        )
    ):
        raise ValueError("preflight diagnostic cannot accept a commit or persistent activity")
    if (
        row["snapshot_available"]
        or row.get("snapshot_target", -1) != -1
        or row.get("settings_state", 5) != 5
    ):
        raise ValueError("four network targets only; no settings repair/snapshot")
    if row["complete"] and not row["program"]:
        raise ValueError("completed full-file action requires fresh page programs")
    return row | counters


def resources(payload, *, target_count=4):
    if type(target_count) is not int or target_count not in (3, 4):
        raise ValueError("fixed network target count required")
    row = loads(payload)
    if (
        not isinstance(row, dict)
        or set(row)
        != {"targets", "originals_verified", "memory_free", "space_available", "space_required"}
        or any(type(v) is not int for v in row.values())
        or row["targets"] != target_count
        or row["originals_verified"] != target_count
        or not 24 * 1048576 <= row["memory_free"] <= 1073741824
        or not 0 < row["space_required"] <= row["space_available"] <= 46 * 1048576
    ):
        raise ValueError("checked four-file custody and memory/space guards required")
    return row


class NetworkSession(Session):
    def __init__(
        self, binding, save, *, target_count=4, preflight_only=False, shared_originals=False
    ):
        if type(target_count) is not int or target_count not in (3, 4):
            raise ValueError("fixed network scope required")
        if type(shared_originals) is not bool or (shared_originals and target_count != 3):
            raise ValueError("shared-original cases are cleanup3-only")
        if binding.action not in (1, 2):
            raise ValueError("network install/restore only")
        self.target_count = target_count
        if type(preflight_only) is not bool or (preflight_only and binding.action != 1):
            raise ValueError("explicit install-scope preflight-only diagnostic required")
        self.preflight_only = preflight_only
        super().__init__(
            binding,
            save,
            selftest_validator=lambda payload: selftest(payload, shared_originals=shared_originals),
            result_validator=lambda payload, action: result(
                payload, action, target_count=target_count, preflight_only=preflight_only
            ),
        )

    def event(self, kind, payload):
        if self.preflight_only and kind in (p.READY, p.PREFLIGHT_INFO):
            raise ValueError("preflight-only diagnostics cannot request a decision")
        if kind not in (p.SELFTEST, p.PREFLIGHT_INFO, p.READY, p.RESULT):
            raise ValueError("event outside four-file network action scope")
        if kind == p.PREFLIGHT_INFO:
            digest = hashlib.sha256(payload).digest()
            if kind in self.seen:
                if self.seen[kind] != digest:
                    raise ValueError("resource evidence changed")
                return None
            if not self.selftest or self.ready or self.result is not None:
                raise ValueError("resource evidence outside preflight")
            self.save("preflight-info.json", payload)
            self.info = resources(payload, target_count=self.target_count)
            self.seen[kind] = digest
            return None
        if kind == p.READY and self.info is None:
            raise ValueError("fresh resource evidence required before READY")
        return super().event(kind, payload)
