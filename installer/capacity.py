"""Conservative whole-install bounds; no flash, USB or mutable backup access."""

from provisioning import file_capsule

MAX_RESERVE = 8 * 1048576


def root_reserve(capsule, pin):
    """Bound new core9 staging on root0 before either phase runs.

    Core9 stores originals in user-config, whose capacity/target7 have their
    own core preflight. Root0 must retain its old pages while staging the full
    replacements. This never credits deleted pages or JFFS2 compression.
    """
    import json

    from firmware.file_writer.prepare import pin_read
    from firmware.tls_probe.package import private_read

    file_capsule.check(capsule, expected_plan=pin_read(pin))
    manifest = json.loads(private_read(capsule / "plan.json", 32768))
    rows = manifest["files"]
    total = sum(row["replacement_bytes"] for row in rows if row["target"] != 7)
    # Small-file nodes, directory entries and the new journal also allocate space.
    reserve = total + 128 * 1024
    if not 0 < reserve <= MAX_RESERVE:
        raise ValueError("bounded commissioning root reserve required")
    return reserve


def checked_reserve(value, preflight_only):
    if type(value) is not int or not 0 <= value <= MAX_RESERVE:
        raise ValueError("bounded integer commissioning space reserve required")
    if value and preflight_only is not True:
        raise ValueError("combined reservation belongs only to the no-commit preflight")
    return value


def passed(row):
    """Accept only an exited, sealed, no-write successful resource preflight."""
    zeros = (
        "initial_error",
        "diagnostic",
        "commit_received",
        "stage_error",
        "window_opened",
        "rw_attempted",
        "transaction_called",
        "rollback_error",
        "journal_error",
        "cleanup_error",
        "attempted",
        "restored",
        "committed",
        "release_error",
        "unmount_errors",
        "seal_error",
        "program",
        "erase",
        "marker",
        "failed",
        "complete",
        "verified",
        "encoding_verified",
        "snapshot_available",
    )
    return (
        all(type(row.get(k)) is int and row[k] == 0 for k in zeros)
        and all(
            type(row.get(k)) is int and row[k] == v
            for k, v in (
                ("preflight_only", 1),
                ("safe_to_restart", 1),
                ("phase", 2),
                ("protected", 1),
                ("error", -2),
                ("preflight_target", -1),
                ("snapshot_target", -1),
                ("settings_state", 5),
            )
        )
        and type(row.get("memory_free")) is int
        and 24 * 1048576 <= row["memory_free"] <= 1073741824
        and all(type(row.get(k)) is int for k in ("space_required", "space_available"))
        and 0 < row["space_required"] <= row["space_available"] <= 46 * 1048576
    )
