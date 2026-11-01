"""Strict four-file evidence ordering; never authorizes a device boot or commit."""

import hashlib

from backend.validation import loads
from firmware.file_writer import protocol as p
from firmware.file_writer.session import Session
from firmware.network_probe.run import validate_payload


def selftest(payload):
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


def result(payload, action):
    row = p.validate_result(payload, action, target_count=4)
    if (
        row["snapshot_available"]
        or row.get("snapshot_target", -1) != -1
        or row.get("settings_state", 5) != 5
    ):
        raise ValueError("four network targets only; no settings repair/snapshot")
    if row["complete"] and not row["program"]:
        raise ValueError("completed full-file action requires fresh page programs")
    return row


def resources(payload):
    row = loads(payload)
    if (
        not isinstance(row, dict)
        or set(row)
        != {"targets", "originals_verified", "memory_free", "space_available", "space_required"}
        or any(type(v) is not int for v in row.values())
        or row["targets"] != 4
        or row["originals_verified"] != 4
        or not 24 * 1048576 <= row["memory_free"] <= 1073741824
        or not 0 < row["space_required"] <= row["space_available"] <= 46 * 1048576
    ):
        raise ValueError("checked four-file custody and memory/space guards required")
    return row


class NetworkSession(Session):
    def __init__(self, binding, save):
        if binding.action not in (1, 2):
            raise ValueError("network install/restore only")
        super().__init__(binding, save, selftest_validator=selftest, result_validator=result)

    def event(self, kind, payload):
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
            self.info = resources(payload)
            self.seen[kind] = digest
            return None
        if kind == p.READY and self.info is None:
            raise ValueError("fresh resource evidence required before READY")
        return super().event(kind, payload)
