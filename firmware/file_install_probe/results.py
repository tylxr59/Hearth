"""Require standalone settings behavior and every synthetic file-transaction case."""

import json

from backend.validation import loads
from firmware.settings_compat_probe.results import exact
from firmware.settings_compat_probe.results import validate as storage_validate

MAX_REPORT = 49152
CLEAN_LOG_MATCHES = 0


def validate(data):
    if len(data) > MAX_REPORT:
        raise ValueError("file lab report bound exceeded")
    storage, cases, processes = [], set(), 0
    for line in data.splitlines():
        row = loads(line)
        if isinstance(row, dict) and row.get("type") == "file_case":
            case = row.get("case")
            if type(case) is not int or case not in range(32) or case in cases:
                raise ValueError("missing/duplicate/unexpected file case")
            exact(row, {"type": "file_case", "case": case, "passed": True})
            cases.add(case)
        elif isinstance(row, dict) and row.get("variant") == "files":
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
            processes += 1
        else:
            storage.append(row)
    if cases != set(range(32)) or processes != 1:
        raise ValueError("file transaction evidence incomplete")
    result = storage_validate(b"\n".join(json.dumps(row).encode() for row in storage))
    return {
        "status": "standalone-settings-and-file-ram-matrix-observed",
        "settings_cases": 36,
        "file_cases": 32,
        "standalone_settings_verified": True,
        "synthetic_value_logs_removed": result["synthetic_value_logs_removed"],
        "installed": False,
        "flash_filesystem_verified": False,
        "full_native_application_verified": False,
        "restoration": "unverified",
    }
