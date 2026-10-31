"""Require standalone settings behavior and every synthetic file-transaction case."""

import json

from backend.validation import loads
from firmware.settings_compat_probe.results import exact
from firmware.settings_compat_probe.results import validate as storage_validate

MAX_REPORT = 49152
CLEAN_LOG_MATCHES = 0


def validate(data, *, require_recovery=True):
    if len(data) > MAX_REPORT:
        raise ValueError("file lab report bound exceeded")
    storage, cases, recovery, processes = [], set(), set(), 0
    for line in data.splitlines():
        row = loads(line)
        if isinstance(row, dict) and row.get("type") == "file_case":
            case = row.get("case")
            if type(case) is not int or case not in range(32) or case in cases:
                raise ValueError("missing/duplicate/unexpected file case")
            exact(row, {"type": "file_case", "case": case, "passed": True})
            cases.add(case)
        elif isinstance(row, dict) and row.get("type") == "recovery_case":
            case = row.get("case")
            if (
                not require_recovery
                or type(case) is not int
                or case not in set(range(24)) - {14}
                or case in recovery
            ):
                raise ValueError("missing/duplicate/unexpected recovery case")
            exact(row, {"type": "recovery_case", "case": case, "passed": True})
            recovery.add(case)
        elif isinstance(row, dict) and row.get("variant") == "files":
            try:
                exact(
                    row,
                    {
                        "type": "compat_process",
                        "variant": "files",
                        "wait_status": 0,
                        "synthetic_secret_log_matches": CLEAN_LOG_MATCHES,
                        "passthrough_log_matches": CLEAN_LOG_MATCHES,
                    },
                )
            except ValueError as exc:
                raise ValueError(
                    "file helper did not complete with a clean process status"
                ) from exc
            processes += 1
        else:
            storage.append(row)
    if cases != set(range(32)) or processes != 1:
        raise ValueError("file transaction evidence incomplete")
    if require_recovery and recovery != set(range(24)) - {14}:
        raise ValueError("interrupted-install recovery evidence incomplete")
    result = storage_validate(b"\n".join(json.dumps(row).encode() for row in storage))
    return {
        "status": "standalone-settings-and-file-ram-matrix-observed",
        "settings_cases": 36,
        "file_cases": 32,
        "recovery_cases": len(recovery),
        "ram_interrupted_install_recovery_verified": require_recovery,
        "standalone_settings_verified": True,
        "synthetic_value_logs_removed": result["synthetic_value_logs_removed"],
        "installed": False,
        "flash_filesystem_verified": False,
        "full_native_application_verified": False,
        "restoration": "unverified",
    }
