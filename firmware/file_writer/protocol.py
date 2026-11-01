"""Bounded, exact-plan USB frames and strict file-action evidence contracts."""

import struct
import zlib
from dataclasses import dataclass

from backend.validation import loads

MAX_PAYLOAD = 16384
END = b"HFW_END1"
SELFTEST = b"HFW_TST1"
READY = b"HFW_RDY1"
RESULT = b"HFW_RES1"
SNAPSHOT = b"HFW_SNP1"
KERNEL_LOG = b"HFW_KLG1"
PREFLIGHT_INFO = b"HFW_INF1"
MAX_SNAPSHOT = 8 + 9 * (24 + 1024 * 1024)
FILE_CASES = set(range(32))
RECOVERY_CASES = set(range(25)) - {14}
REENCODE_CASES = set(range(13))


@dataclass(frozen=True)
class Binding:
    plan: bytes
    receipt: bytes
    action: int

    def __post_init__(self):
        if (
            type(self.plan) is not bytes
            or len(self.plan) != 32
            or type(self.receipt) is not bytes
            or len(self.receipt) != 32
            or type(self.action) is not int
            or self.action not in (1, 2, 3)
        ):
            raise ValueError("fixed private plan/receipt/action required")

    def prefix(self, magic):
        if magic not in (
            SELFTEST,
            READY,
            RESULT,
            SNAPSHOT,
            KERNEL_LOG,
            PREFLIGHT_INFO,
            b"HFW_ACK1",
            b"HFW_RUN1",
            b"HFW_STOP",
        ):
            raise ValueError("unknown fixed file-action message")
        return magic + self.plan + self.receipt + struct.pack("<I", self.action)


class Decoder:
    def __init__(self, binding):
        self.binding = binding
        self.buffer = bytearray()
        self.rejected = 0

    def feed(self, chunk):
        if len(chunk) > 65536:
            raise ValueError("file-action receive chunk exceeds bound")
        self.buffer.extend(chunk)
        events = []
        prefixes = {
            kind: self.binding.prefix(kind)
            for kind in (SELFTEST, READY, RESULT, SNAPSHOT, KERNEL_LOG, PREFLIGHT_INFO)
        }
        while True:
            candidates = [(self.buffer.find(prefix), kind) for kind, prefix in prefixes.items()]
            candidates = [(position, kind) for position, kind in candidates if position >= 0]
            if not candidates:
                if b"HFW_BOOTSTRAP_FAILED_V1\n" in self.buffer:
                    raise ValueError("root action launch failed before commit")
                if b"HFSNAP1\n" in self.buffer:
                    raise ValueError("fallback reader booted; no commit permitted")
                self.buffer = self.buffer[-75:]
                break
            position, kind = min(candidates)
            if position:
                del self.buffer[:position]
            if kind == READY:
                events.append((kind, b""))
                del self.buffer[:76]
                continue
            if len(self.buffer) < 84:
                break
            length, crc = struct.unpack_from("<II", self.buffer, 76)
            if length > (MAX_SNAPSHOT if kind == SNAPSHOT else MAX_PAYLOAD):
                raise ValueError("file-action report exceeds bound")
            total = 84 + length + 8
            if len(self.buffer) < total:
                break
            frame = bytes(self.buffer[:total])
            payload = frame[84:-8]
            if frame[-8:] != END or zlib.crc32(payload) != crc:
                self.rejected += 1
                events.append((b"rejected", frame))
                if self.rejected > 4:
                    raise ValueError("file-action synchronization/integrity limit exceeded")
                del self.buffer[:1]
                continue
            events.append((kind, payload))
            del self.buffer[:total]
        if len(self.buffer) > MAX_SNAPSHOT + 92:
            raise ValueError("unterminated file-action frame exceeds bound")
        return events


def validate_selftest(payload, *, reencode_cases=13):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("selftest evidence exceeds bound")
    if reencode_cases not in (10, 13):
        raise ValueError("reviewed current or historical reencode matrix required")
    expected = {
        "file_case": FILE_CASES,
        "recovery_case": RECOVERY_CASES,
        "reencode_case": set(range(reencode_cases)),
    }
    seen, process, stdout = {kind: set() for kind in expected}, None, 0
    for line in payload.splitlines(keepends=True):
        row = loads(line)
        if not isinstance(row, dict):
            raise ValueError("selftest record required")  # noqa: TRY004
        kind = row.get("type")
        if kind in seen:
            case = row.get("case")
            allowed = expected[kind]
            if (
                set(row) != {"type", "case", "passed"}
                or type(case) is not int
                or case not in allowed
                or case in seen[kind]
                or row["passed"] is not True
            ):
                raise ValueError("selftest case missing/duplicate/invalid")
            seen[kind].add(case)
            stdout += len(line)
        elif kind == "file_selftest_process":
            if process is not None or set(row) != {
                "type",
                "wait_status",
                "stderr_bytes",
                "stderr_dropped",
                "stdout_bytes",
            }:
                raise ValueError("one exact selftest process record required")
            if any(type(row[key]) is not int for key in row if key != "type"):
                raise ValueError("integer selftest process fields required")
            process = row
        else:
            # Raw diagnostics stay in the private frame, never become a pass.
            raise ValueError("selftest diagnostic or unexpected record present")
    if seen != expected:
        raise ValueError("all required original RAM selftests required")
    if process != {
        "type": "file_selftest_process",
        "wait_status": 0,
        "stderr_bytes": 0,
        "stderr_dropped": 0,
        "stdout_bytes": stdout,
    }:
        raise ValueError("selftest process or exact stdout completion failed")
    return {
        "status": "file-action-ram-selftests-observed",
        "cases": 56 + reencode_cases,
        "writes_started": False,
    }


FIELDS = {
    "type",
    "action",
    "initial_error",
    "preflight_target",
    "commit_received",
    "stage_error",
    "window_opened",
    "rw_attempted",
    "transaction_called",
    "error",
    "rollback_error",
    "journal_error",
    "cleanup_error",
    "attempted",
    "restored",
    "committed",
    "release_error",
    "unmount_errors",
    "seal_error",
    "verified",
    "safe_to_restart",
    "complete",
    "phase",
    "protected",
    "program",
    "erase",
    "marker",
    "failed",
    "snapshot_available",
    "encoding_verified",
}
FLAGS = {
    "commit_received",
    "window_opened",
    "transaction_called",
    "rollback_error",
    "journal_error",
    "cleanup_error",
    "committed",
    "release_error",
    "seal_error",
    "verified",
    "safe_to_restart",
    "complete",
    "protected",
    "snapshot_available",
    "encoding_verified",
}


def validate_result(payload, action):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("file-action result exceeds bound")
    row = loads(payload)
    if (
        not isinstance(row, dict)
        or not FIELDS <= set(row) <= FIELDS | {"diagnostic", "snapshot_target", "settings_state"}
        or row["type"] != "file_action"
        or any(type(row[key]) is not int for key in row if key != "type")
        or type(action) is not int
        or action not in (1, 2, 3)
        or row["action"] != action
    ):
        raise ValueError("exact bound file-action result required")
    if (
        not 0 <= row.get("diagnostic", 0) <= 200
        or not -1 <= row.get("snapshot_target", -1) <= 8
        or not 0 <= row.get("settings_state", 5) <= 7
    ):
        raise ValueError("bounded startup diagnostic fields required")
    if (
        any(row[key] not in (0, 1) for key in FLAGS)
        or row["initial_error"] not in (0, 1, 2)
        or not -1 <= row["preflight_target"] <= 8
        or not 0 <= row["stage_error"] <= 5
        or not -8 <= row["error"] <= 0
        or row["rw_attempted"] not in (0, 1, 3)
        or not 0 <= row["unmount_errors"] <= 3
        or row["phase"] not in (0, 1, 2)
        or not 0 <= row["attempted"] <= 511
        or not 0 <= row["restored"] <= 511
        or row["restored"] & ~row["attempted"]
        or any(not 0 <= row[key] < 2**32 for key in ("program", "erase", "marker", "failed"))
        or row["failed"] > row["program"] + row["erase"] + row["marker"]
    ):
        raise ValueError("file-action result field range invalid")
    if row["initial_error"] and (
        row["commit_received"] or row["rw_attempted"] or row["transaction_called"]
    ):
        raise ValueError("action started after failed initial preflight")
    if row["transaction_called"] and (
        not row["commit_received"] or not row["window_opened"] or row["rw_attempted"] != 3
    ):
        raise ValueError("transaction lacks commit/window/remount evidence")
    if row["rw_attempted"] and (not row["commit_received"] or not row["window_opened"]):
        raise ValueError("writable attempt lacks scoped commit")
    if row["window_opened"] and not row["commit_received"]:
        raise ValueError("write window lacks scoped commit")
    if row["verified"] and not row["rw_attempted"]:
        raise ValueError("post-write verification lacks writable attempt")
    if row["encoding_verified"] and (not row["verified"] or not row["rw_attempted"]):
        raise ValueError("encoding verification lacks completed post-write readback")
    if (row["attempted"] or row["restored"] or row["committed"]) and not row["transaction_called"]:
        raise ValueError("transaction outcome lacks invocation evidence")
    if row["committed"] and (
        action != 1 or row["attempted"] != 511 or row["error"] or row["restored"]
    ):
        raise ValueError("committed outcome contradicts complete installation")
    if row["snapshot_available"] and row["initial_error"] != 2:
        raise ValueError("changed-file snapshot lacks failed initial preflight")
    if row["safe_to_restart"] and (
        row["release_error"]
        or row["unmount_errors"]
        or row["seal_error"]
        or row["phase"] != 2
        or row["protected"] != 1
        or row["failed"]
        or (row["rw_attempted"] and (not row["verified"] or not row["encoding_verified"]))
        or (not row["rw_attempted"] and (row["program"] or row["erase"] or row["marker"]))
    ):
        raise ValueError("restart safety evidence incomplete")
    if row["complete"]:
        required = {
            "initial_error": 0,
            "commit_received": 1,
            "stage_error": 0,
            "window_opened": 1,
            "rw_attempted": 3,
            "transaction_called": 1,
            "error": 0,
            "rollback_error": 0,
            "journal_error": 0,
            "cleanup_error": 0,
            "attempted": 511,
            "committed": int(action == 1),
            "restored": 0 if action == 1 else 511,
            "release_error": 0,
            "unmount_errors": 0,
            "seal_error": 0,
            "verified": 1,
            "encoding_verified": 1,
            "safe_to_restart": 1,
            "phase": 2,
            "protected": 1,
            "failed": 0,
        }
        if any(row[key] != value for key, value in required.items()):
            raise ValueError("complete action lacks exact transaction/readback/protection evidence")
        if action == 3 and not row["program"]:
            raise ValueError("forced reencoding requires actual fresh page programs")
    return row


def snapshot_frame(payload, binding):
    """Reuse the strict snapshot/custody format without accepting arbitrary files."""
    from firmware.file_snapshot.run import END as SNAP_END
    from firmware.file_snapshot.run import MAGIC, decode

    if len(payload) > MAX_SNAPSHOT:
        raise ValueError("changed-file snapshot exceeds bound")
    frame = (
        MAGIC
        + binding.plan
        + struct.pack("<II", len(payload), zlib.crc32(payload))
        + payload
        + SNAP_END
    )
    return frame, decode(frame, binding.plan)
