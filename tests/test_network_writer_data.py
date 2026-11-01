"""New large-file mapping boundary: independent synthetic data and real host VM."""

import os
import subprocess

import pytest

from provisioning.native_network import FixedSpan
from provisioning.network_plan import header, make_plan


@pytest.fixture(scope="module")
def mapped(tmp_path_factory):
    root = tmp_path_factory.mktemp("network-mapped")
    data = [bytes(range(256)) * n for n in (17000, 1800, 17, 48)]
    plans = [
        make_plan(i, d, FixedSpan(4090, b"\xfa\xfb\xfc\xfd\xfe\xff\x00\x01", b"changed!"))
        for i, d in enumerate(data)
    ]
    (root / "plan.h").write_bytes(header(plans, [0o755, 0o755, 0o644, 0o644], b"p" * 32, b"r" * 32))
    command = [
        "clang",
        "-DHEARTH_HOST_LAB",
        "-DHEARTH_NETWORK_ADAPTER",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fsanitize=address,undefined",
        "-I" + str(root),
        "tests/network_data_harness.c",
        "firmware/network_writer/data.c",
        "firmware/file_install/posix.c",
        "firmware/file_install/transaction.c",
        "firmware/network_update/hash.c",
        "firmware/network_update/stream.c",
        "-o",
        str(root / "test"),
    ]
    subprocess.run(command, check=True, capture_output=True)
    return root / "test", data


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "missing",
        "symlink",
        "hardlink",
        "writable",
        "executable",
        "truncated",
        "outside-span",
        "inside-span",
        "directory-mode",
    ],
)
def test_cow_full_file_verification_refuses_changed_inputs_and_preserves_sources(
    mapped, tmp_path, fault
):
    exe, data = mapped
    tmp_path.chmod(0o700)
    for i, d in enumerate(data):
        p = tmp_path / str(i)
        p.write_bytes(d)
        p.chmod(0o400)
    p = tmp_path / "1"
    if fault == "missing":
        p.unlink()
    elif fault == "symlink":
        p.rename(tmp_path / "actual")
        p.symlink_to("actual")
    elif fault == "hardlink":
        os.link(p, tmp_path / "alias")
    elif fault == "writable":
        p.chmod(0o600)
    elif fault == "executable":
        p.chmod(0o500)
    elif fault in ("truncated", "outside-span", "inside-span"):
        p.chmod(0o600)
        d = data[1]
        if fault == "truncated":
            d = d[:-1]
        else:
            at = 4091 if fault == "inside-span" else 0
            d = d[:at] + bytes([d[at] ^ 1]) + d[at + 1 :]
        p.write_bytes(d)
        p.chmod(0o400)
    elif fault == "directory-mode":
        tmp_path.chmod(0o755)
    before = {f.name: f.read_bytes() for f in tmp_path.iterdir() if f.is_file()}
    result = subprocess.run([str(exe), str(tmp_path)], capture_output=True, check=True)
    assert not result.stderr
    assert result.stdout == (b"mapped-and-verified\n" if fault == "none" else b"refused\n")
    assert before == {f.name: f.read_bytes() for f in tmp_path.iterdir() if f.is_file()}


def test_large_mapped_files_install_and_restore_exact_originals(mapped, tmp_path):
    from provisioning.network_backup import TARGETS

    exe, data = mapped
    originals = tmp_path / "originals"
    root = tmp_path / "root"
    originals.mkdir(mode=0o700)
    root.mkdir(mode=0o700)
    for i, (path, d) in enumerate(zip(TARGETS, data)):
        p = originals / str(i)
        p.write_bytes(d)
        p.chmod(0o400)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(d)
        target.chmod(0o755 if i < 2 else 0o644)
    run = subprocess.run([str(exe), str(originals), str(root)], capture_output=True, check=True)
    assert run.stdout == b"mapped-and-verified\n" and not run.stderr
    for i, (path, d) in enumerate(zip(TARGETS, data)):
        assert (root / path).read_bytes() == d
        assert (originals / str(i)).read_bytes() == d
        assert (root / path).stat().st_mode & 0o777 == (0o755 if i < 2 else 0o644)
