"""Validate complete bounded observations, without mistaking old writer bugs for fixes."""

import re

from backend.validation import loads

CASES = (
    "normal",
    "file_open",
    "header_write",
    "entry_error",
    "entry_short",
    "footer_write",
    "file_sync",
    "file_close",
    "rename",
    "dir_open",
    "dir_sync",
    "dir_close",
)
FIELDS = {
    "type",
    "case",
    "injected",
    "first_result",
    "first_file_opens",
    "first_renames",
    "first_reload_result",
    "first_new",
    "first_old",
    "retry_result",
    "retry_file_opens",
    "retry_renames",
    "retry_reload_result",
    "retry_new",
    "retry_old",
    "canary_ok",
}


def validate(data):
    if len(data) > 16384:
        raise ValueError("settings report limit exceeded")
    rows = [loads(line) for line in data.splitlines()]
    clean = []
    truncated = False
    for row in rows:
        if isinstance(row, dict) and row.get("type") == "settings_stderr":
            if (
                set(row) != {"type", "hex"}
                or not isinstance(row["hex"], str)
                or not re.fullmatch(r"(?:[0-9a-f]{2}){1,128}", row["hex"])
            ):
                raise ValueError("invalid private settings diagnostic")
            continue  # retain privately; never print decoded native log output
        if isinstance(row, dict) and row.get("type") == "settings_stderr_truncated":
            if (
                truncated
                or set(row) != {"type", "bytes_dropped"}
                or type(row["bytes_dropped"]) is not int
                or not 1 <= row["bytes_dropped"] <= 1048576
            ):
                raise ValueError("invalid diagnostic truncation record")
            truncated = True
            continue
        clean.append(row)
    if (
        len(clean) != 14
        or clean[-1] != {"type": "settings_complete", "passed": True}
        or clean[-1].get("passed") is not True
    ):
        raise ValueError("settings run incomplete")
    process = clean[-2]
    if (
        process != {"type": "settings_process", "wait_status": 0}
        or type(process.get("wait_status")) is not int
    ):
        raise ValueError("settings helper did not exit successfully")
    observations = []
    for case, row in zip(CASES, clean[:-2], strict=True):
        if (
            not isinstance(row, dict)
            or set(row) != FIELDS
            or row["type"] != "settings_case"
            or row["case"] != case
            or row["canary_ok"] is not True
        ):
            raise ValueError("unexpected settings case/ABI guard")
        for key in FIELDS - {"type", "case", "canary_ok"}:
            if type(row[key]) is not int or not -1024 <= row[key] <= 1024:
                raise ValueError("invalid bounded settings result")
        if row["injected"] != int(case != "normal") or row["first_file_opens"] != 1:
            raise ValueError("fault or write interception not observed")
        for key in ("first_renames", "retry_file_opens", "retry_renames"):
            if row[key] not in (0, 1):
                raise ValueError("unexpected extra settings write")
        for prefix in ("first", "retry"):
            if (
                not 0 <= row[prefix + "_new"] <= 3
                or not 0 <= row[prefix + "_old"] <= 3
                or row[prefix + "_new"] & row[prefix + "_old"]
            ):
                raise ValueError("invalid synthetic readback masks")
        if case == "normal" and any(
            row[k] != v
            for k, v in {
                "first_result": 0,
                "first_renames": 1,
                "first_reload_result": 0,
                "first_new": 3,
                "first_old": 0,
                "retry_result": 0,
                "retry_file_opens": 0,
                "retry_renames": 0,
                "retry_reload_result": 0,
                "retry_new": 3,
                "retry_old": 0,
            }.items()
        ):
            raise ValueError("normal settings write/reload baseline failed")
        observations.append({k: row[k] for k in FIELDS - {"type", "canary_ok"}})
    return {
        "status": "native-settings-fault-observations-received",
        "cases": len(CASES),
        "storage": "synthetic RAM files only",
        "native_writer_fixed": False,
        "installed": False,
        "power_loss_or_restoration_verified": False,
        "observations": observations,
    }
