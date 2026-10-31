"""Require the original baseline, corrected failures/retries and streaming log checks."""

import re

from backend.validation import Invalid, loads
from firmware.settings_probe.results import CASES

ALLOCATIONS = (
    "update_allocation",
    "new_key_allocation",
    "new_value_allocation",
    "hash_insertion",
    "aliased_value",
)


def io_expected(variant, case, lost_mask=1):
    row = {
        "type": "compat_case",
        "variant": variant,
        "case": case,
        "injected": int(case != "normal"),
        "first_result": 0,
        "first_file_opens": 1,
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
        "canary_ok": True,
    }
    if case == "normal":
        return row
    row.update(
        first_result=-100 if case in ("file_open", "dir_open") else -103,
        retry_file_opens=1,
        retry_renames=1,
    )
    if case in (
        "file_open",
        "header_write",
        "footer_write",
        "file_sync",
        "file_close",
        "rename",
        "entry_error",
        "entry_short",
    ):
        row.update(first_new=0, first_old=3, first_renames=int(case == "rename"))
    if variant == "original" and case in ("entry_error", "entry_short"):
        row.update(
            first_result=0, first_renames=1, first_old=0, retry_file_opens=0, retry_renames=0
        )
        if case == "entry_error":
            row.update(first_new=lost_mask, retry_new=lost_mask)
        else:
            row.update(first_new=0, retry_new=0, first_reload_result=-8, retry_reload_result=-8)
    if variant == "original" and case == "dir_sync":
        row.update(retry_file_opens=0, retry_renames=0)
    return row


def allocation_expected(case):
    return {
        "type": "compat_allocation",
        "variant": "candidate",
        "case": case,
        "first_result": 0 if case == "aliased_value" else -2,
        "injected": int(case != "aliased_value"),
        "old_freed_on_failure": 0,
        "preserved": True,
        "retry_result": 0,
        "restored": True,
        "canary_ok": True,
    }


def exact(row, expected):
    if (
        not isinstance(row, dict)
        or set(row) != set(expected)
        or any(type(row[k]) is not type(v) or row[k] != v for k, v in expected.items())
    ):
        raise ValueError("storage behavior did not match the baseline/correction contract")


def validate(data):
    if len(data) > 32768:
        raise ValueError("comparison report limit")
    rows = [loads(line) for line in data.splitlines()]
    clean = []
    captured = {v: 0 for v in ("original", "candidate")}
    dropped = set()
    for row in rows:
        if isinstance(row, dict) and row.get("type") in (
            "compat_stderr",
            "compat_stderr_truncated",
        ):
            v = row.get("variant")
            if not isinstance(v, str) or v not in captured:
                raise ValueError("unexpected diagnostic variant")
            if row["type"] == "compat_stderr":
                if (
                    set(row) != {"type", "variant", "hex"}
                    or not isinstance(row["hex"], str)
                    or not re.fullmatch(r"(?:[0-9a-f]{2}){1,128}", row["hex"])
                ):
                    raise ValueError("invalid private diagnostic chunk")
                captured[v] += len(row["hex"]) // 2
                if captured[v] > 2048:
                    raise ValueError("private diagnostic budget exceeded")
            else:
                if (
                    set(row) != {"type", "variant", "bytes_dropped"}
                    or v in dropped
                    or type(row["bytes_dropped"]) is not int
                    or not 1 <= row["bytes_dropped"] <= 1048576
                ):
                    raise ValueError("invalid diagnostic truncation")
                dropped.add(v)
            continue
        clean.append(row)
    if len(clean) != 34:
        raise ValueError("comparison matrix incomplete")
    exact(clean[-1], {"type": "compat_complete", "passed": True})
    seen = set()
    helpers = set()
    processes = set()
    allocations = set()
    for row in clean[:-1]:
        if not isinstance(row, dict):
            raise Invalid("comparison row must be an object")
        kind = row.get("type")
        variant = row.get("variant")
        if not isinstance(variant, str) or variant not in captured:
            raise ValueError("unexpected comparison variant")
        if kind == "compat_case":
            case = row.get("case")
            if not isinstance(case, str) or case not in CASES or (variant, case) in seen:
                raise ValueError("unexpected/duplicate I/O case")
            mask = row.get("first_new") if variant == "original" and case == "entry_error" else 1
            if type(mask) is not int or mask not in (1, 2):
                raise ValueError("original failed entry must lose exactly one value")
            exact(row, io_expected(variant, case, mask))
            seen.add((variant, case))
        elif kind == "compat_allocation":
            case = row.get("case")
            if not isinstance(case, str) or case not in ALLOCATIONS or case in allocations:
                raise ValueError("unexpected/duplicate allocation case")
            exact(row, allocation_expected(case))
            allocations.add(case)
        elif kind == "compat_helper":
            if (
                set(row) != {"type", "variant", "bindings_verified", "suppressed_logs"}
                or row["bindings_verified"] is not True
                or type(row["suppressed_logs"]) is not int
                or not 0 <= row["suppressed_logs"] <= 1048576
                or (row["suppressed_logs"] == 0) != (variant == "original")
                or variant in helpers
            ):
                raise ValueError("candidate binding/log scope not verified")
            helpers.add(variant)
        elif kind == "compat_process":
            if (
                set(row)
                != {
                    "type",
                    "variant",
                    "wait_status",
                    "synthetic_secret_log_matches",
                    "passthrough_log_matches",
                }
                or type(row["wait_status"]) is not int
                or row["wait_status"] != 0
                or type(row["passthrough_log_matches"]) is not int
                or row["passthrough_log_matches"] != 1
                or type(row["synthetic_secret_log_matches"]) is not int
                or not 0 <= row["synthetic_secret_log_matches"] <= 1048576
                or variant in processes
            ):
                raise ValueError("process/variadic log passthrough not verified")
            if (variant == "candidate" and row["synthetic_secret_log_matches"] != 0) or (
                variant == "original" and row["synthetic_secret_log_matches"] < 2
            ):
                raise ValueError("synthetic secret-log baseline/correction not verified")
            processes.add(variant)
        else:
            raise ValueError("unexpected comparison row")
    if (
        seen != {(v, c) for v in captured for c in CASES}
        or allocations != set(ALLOCATIONS)
        or helpers != set(captured)
        or processes != set(captured)
        or any(captured[v] != 2048 for v in dropped)
    ):
        raise ValueError("missing comparison evidence")
    return {
        "status": "native-storage-correction-matrix-observed",
        "io_cases": 24,
        "allocation_alias_cases": 5,
        "synthetic_value_logs_removed": True,
        "unrelated_variadic_log_forwarding_verified": True,
        "installed": False,
        "full_native_application_verified": False,
        "restoration": "unverified",
        "physical_hvac_verified": False,
    }
