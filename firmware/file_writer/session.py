"""One RAM session's evidence/commit ordering; no USB or automatic authorization."""

import hashlib

from backend.validation import loads
from firmware.file_writer import protocol as p


class Session:
    def __init__(self, binding, save):
        self.binding, self.save = binding, save
        self.selftest = self.ready = self.committed = self.aborted = False
        self.snapshot = self.result = None
        self.info = None
        self.seen = {}

    def event(self, kind, payload):
        digest = hashlib.sha256(payload).digest()
        if kind in self.seen:
            if self.seen[kind] != digest:
                raise ValueError("cached evidence changed within one RAM session")
            return None
        if self.result is not None:
            raise ValueError("new evidence after terminal result")
        if kind == b"rejected":
            raise ValueError("USB integrity failure; no automatic retry")
        if kind == p.SELFTEST:
            self.save("selftest.jsonl", payload)
            p.validate_selftest(payload)
            self.selftest = True
            reply = self.binding.prefix(b"HFW_ACK1")
        elif kind == p.READY:
            if not self.selftest:
                raise ValueError("real-file preflight preceded verified RAM selftests")
            if self.binding.action == 3 and self.info is None:
                raise ValueError("repair preflight metadata required before READY")
            self.ready = True
            reply = None
        elif kind == p.SNAPSHOT:
            if not self.selftest or self.ready:
                raise ValueError("changed-file snapshot in inconsistent session")
            frame, records = p.snapshot_frame(payload, self.binding)
            self.save("changed-files.bin", frame)
            self.snapshot = records
            reply = None
        elif kind == p.PREFLIGHT_INFO:
            row = loads(payload)
            if (
                not self.selftest
                or self.ready
                or self.binding.action != 3
                or not isinstance(row, dict)
                or set(row) != {"missing_originals", "settings_state", "write_policy"}
                or any(type(value) is not int for value in row.values())
                or row["write_policy"] != 0
                or row["settings_state"] not in (0, 1)
                or not 0 <= row["missing_originals"] <= 511
                or row["missing_originals"] & 48
                or bool(row["missing_originals"] & 128) != bool(row["settings_state"])
            ):
                raise ValueError("exact bounded repair preflight metadata required")
            self.save("preflight-info.json", payload)
            self.info = row
            reply = None
        elif kind == p.KERNEL_LOG:
            if not self.selftest or self.ready or len(payload) > p.MAX_PAYLOAD:
                raise ValueError("kernel evidence in inconsistent session")
            self.save("kernel-log.bin", payload)
            reply = None
        elif kind == p.RESULT:
            self.save("result.json", payload)
            row = p.validate_result(payload, self.binding.action)
            if not self.selftest or row["commit_received"] != int(self.committed):
                raise ValueError("result disagrees with host commit history")
            if bool(row["snapshot_available"]) != (self.snapshot is not None):
                raise ValueError("changed-file snapshot completion missing/inconsistent")
            self.result = row
            reply = None
        else:
            raise ValueError("unknown file-action event")
        self.seen[kind] = digest
        return reply

    def decide(self, commit):
        if type(commit) is not bool or not self.ready or self.result is not None:
            raise ValueError("live verified preflight required before decision")
        if self.committed or self.aborted:
            raise ValueError("one decision only; no logical command retry")
        if commit:
            self.committed = True
        else:
            self.aborted = True
        return self.binding.prefix(b"HFW_RUN1" if commit else b"HFW_STOP")
