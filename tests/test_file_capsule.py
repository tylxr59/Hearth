import hashlib
import os
import shutil
import subprocess
from dataclasses import replace

import pytest

from firmware.file_snapshot.run import decode
from provisioning import file_backup as custody
from provisioning import file_capsule as capsule
from tests.test_file_snapshot_profile import frame

SESSION = b"s" * 32


@pytest.fixture
def preparation(tmp_path):
    tmp_path.chmod(0o700)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir(mode=0o700)
    data = frame()
    capture = snapshot / "capture.bin"
    capture.write_bytes(data)
    capture.chmod(0o600)
    records = decode(data, SESSION)
    collection_plan = hashlib.sha256(
        b"read-only-root0-snapshot-v1\n" + "\n".join(custody.TARGETS).encode()
    ).digest()
    custody.preserve(
        snapshot / "backup", records, session=SESSION, plan=collection_plan, native_root="root0"
    )
    modes = {1: 0o644, 2: 0o644, 4: 0o444, 5: 0o750, 7: 0o600, 8: 0o600}
    replacements = tuple(
        capsule.Replacement(i, modes.get(i, old.mode), b"new\x00bytes\xff")
        for i, old in enumerate(records)
    )
    return snapshot, replacements, tmp_path / "capsule"


def prepare(parts, **changes):
    snapshot, replacements, output = parts
    scope = {"session": SESSION, "native_partition": "primary", "software_version": "5.9.4-5"}
    return capsule.prepare(snapshot, replacements, output, **(scope | changes))


def test_exact_plan_has_new_custody_binding_and_no_installation(preparation):
    snapshot, _, output = preparation
    plan = prepare(preparation)
    result = capsule.check(output, expected_plan=plan)
    assert result["status"] == "offline-plan-bound-not-installable"
    assert not result["installed"] and not result["target_receipt_enforced"]
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in output.iterdir() if p.is_file())
    assert (snapshot / "backup/receipt.json").read_bytes() != (
        output / "backup/receipt.json"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        prepare(preparation)


@pytest.mark.parametrize(
    "key,value",
    [("session", b"x" * 32), ("native_partition", "secondary"), ("software_version", "unknown")],
)
def test_wrong_source_scope_refused_before_output(preparation, key, value):
    with pytest.raises(ValueError):
        prepare(preparation, **{key: value})
    assert not preparation[2].exists()


@pytest.mark.parametrize("fault", ["mode", "order", "empty", "oversized", "missing"])
def test_replacement_scope_refused(preparation, fault):
    source, replacements, output = preparation
    replacements = list(replacements)
    if fault == "mode":
        replacements[7] = replace(replacements[7], mode=0o644)
    elif fault == "order":
        replacements[0], replacements[1] = replacements[1], replacements[0]
    elif fault == "empty":
        replacements[3] = replace(replacements[3], data=b"")
    elif fault == "oversized":
        replacements[0] = replace(replacements[0], data=b"x" * (custody.LIMIT + 1))
    else:
        replacements.pop()
    with pytest.raises(ValueError):
        prepare((source, replacements, output))
    assert not output.exists()


def test_bad_original_custody_prevents_rebinding(preparation):
    source, _, output = preparation
    (source / "backup/0.original").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        prepare(preparation)
    assert not output.exists()


@pytest.mark.parametrize(
    "name", ["capsule.h", "0.replacement", "capture.bin", "plan.json", "backup/receipt.json"]
)
def test_capsule_reverification_catches_every_artifact_class(preparation, name):
    plan = prepare(preparation)
    output = preparation[2]
    (output / name).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        capsule.check(output, expected_plan=plan)


def test_external_plan_pin_is_required(preparation):
    prepare(preparation)
    with pytest.raises(ValueError):
        capsule.check(preparation[2], expected_plan=b"x" * 32)


def test_same_snapshot_and_replacements_reproduce_the_plan_and_receipt(preparation):
    source, replacements, first = preparation
    plan = prepare(preparation)
    second = first.parent / "capsule-repro"
    assert prepare((source, replacements, second)) == plan
    for path in first.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()
    changed = list(replacements)
    changed[3] = replace(changed[3], data=changed[3].data + b"modified")
    third = first.parent / "capsule-changed"
    assert prepare((source, changed, third)) != plan


def test_generated_data_header_compiles_without_executing_firmware(preparation):
    if not shutil.which("clang"):
        pytest.skip("Clang required")
    prepare(preparation)
    output = preparation[2]
    test = output / "header-check.c"
    test.write_text(
        '#include "capsule.h"\nint main(void) { return hearth_capsule_count != 9 || '
        "hearth_capsule_changes[0].replacement.size != 10 || "
        "sizeof(hearth_capsule_plan_id) != 32; }\n"
    )
    # Compilation only: these are synthetic bytes, and no native libraries link.
    subprocess.run(
        [
            "clang",
            "--target=arm-linux-gnueabihf",
            "-ffreestanding",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            "firmware/file_install",
            "-c",
            str(test),
            "-o",
            str(output / "header-check.o"),
        ],
        capture_output=True,
        check=True,
    )


def test_failed_disk_write_retains_partial_output_without_valid_capsule(preparation, monkeypatch):
    real_write = os.write
    count = 0

    def write(fd, data):
        nonlocal count
        count += 1
        if count == 4:
            raise OSError("injected disk fault")
        return real_write(fd, data)

    monkeypatch.setattr(custody.os, "write", write)
    with pytest.raises(OSError):
        prepare(preparation)
    assert preparation[2].is_dir()
    assert not (preparation[2] / "capsule.h").exists()
