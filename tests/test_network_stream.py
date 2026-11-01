import hashlib
import shutil
import struct
import subprocess
from dataclasses import replace

import pytest

from provisioning import network_backup, network_plan
from provisioning.native_network import FixedSpan
from tests.test_native_network import CONFIG, image
from tests.test_network_snapshot import snapshot


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang needed for original stream-core sanitizers")
    path = tmp_path_factory.mktemp("network-stream") / "stream"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "tests/network_stream_harness.c",
            "firmware/network_update/hash.c",
            "firmware/network_update/stream.c",
            "-o",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def invoke(harness, mode, plan, data, fault=0):
    result = subprocess.run(
        [str(harness), mode, str(fault)],
        input=plan.binary() + data,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert not result.stderr
    status, reads, writes, rewinds, length = struct.unpack_from("<i4I", result.stdout)
    assert len(result.stdout) == 20 + length
    return status, reads, writes, rewinds, result.stdout[20:]


@pytest.mark.parametrize(
    "length", (0, 1, 55, 56, 63, 64, 65, 127, 128, 4095, 4096, 4097, 1000000, 6 * 1048576)
)
def test_bounded_hash_matches_independent_hashlib_and_padding_edges(harness, length):
    data = (bytes(range(256)) * ((length + 255) // 256))[:length]
    result = subprocess.run(
        [str(harness), "hash", "137"], input=data, capture_output=True, check=True, timeout=10
    )
    assert result.stdout == hashlib.sha256(data).digest() and not result.stderr


def test_hash_refuses_more_than_the_largest_target(harness):
    result = subprocess.run(
        [str(harness), "hash", "4096"],
        input=b"a" * (6 * 1048576 + 1),
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2 and not result.stdout and not result.stderr


def sample(offset=4090, width=40):
    data = bytes(range(256)) * 40 + b"tail"
    span = FixedSpan(
        offset, data[offset : offset + width], b"local replacement".ljust(width, b"\0")
    )
    return data, span, network_plan.make_plan(0, data, span)


@pytest.mark.parametrize("offset,width", ((0, 40), (4090, 40), (4095, 64), (4096, 40), (10204, 40)))
def test_preflight_and_complete_copy_bind_outside_span_and_chunk_boundaries(harness, offset, width):
    data, span, plan = sample(offset, width)
    status, _, writes, _, out = invoke(harness, "preflight", plan, data)
    assert status == 0 and writes == 0 and not out
    status, _, writes, _, out = invoke(harness, "copy", plan, data)
    assert status == 0 and writes and out == span.apply(data)
    assert invoke(harness, "verify", plan, out)[0] == 0
    status, _, _, _, out = invoke(harness, "original", plan, data)
    assert status == 0 and out == data


@pytest.mark.parametrize("fault", (1, 2, 3, 4))
def test_short_and_interrupted_reads_writes_retain_exact_copy(harness, fault):
    data, span, plan = sample()
    status, _, _, _, out = invoke(harness, "copy", plan, data, fault)
    assert status == 0 and out == span.apply(data)


@pytest.mark.parametrize("fault", (5, 6, 7, 8, 9, 10, 11, 12, 13, 14))
def test_io_faults_extra_data_and_retry_limits_stop_without_success(harness, fault):
    data, _, plan = sample()
    assert invoke(harness, "copy", plan, data, fault)[0] == -1


@pytest.mark.parametrize("fault", ("outside", "span", "sourcehash", "candidatehash"))
def test_preflight_refuses_mismatch_without_any_write(harness, fault):
    data, _, plan = sample()
    if fault == "outside":
        data = data[:-1] + bytes([data[-1] ^ 1])
    elif fault == "span":
        data = (
            data[: plan.span.offset]
            + bytes([data[plan.span.offset] ^ 1])
            + data[plan.span.offset + 1 :]
        )
    elif fault == "sourcehash":
        plan = replace(plan, original_hash=b"x" * 32)
    else:
        plan = replace(plan, replacement_hash=b"x" * 32)
    status, _, writes, _, out = invoke(harness, "preflight", plan, data)
    assert status == -1 and writes == 0 and not out


@pytest.mark.parametrize("field,value", (("target", 4), ("size", 0), ("size", 6 * 1048576 + 1)))
def test_invalid_c_plan_never_invokes_io(harness, field, value):
    data, _, plan = sample()
    plan = replace(plan, **{field: value})
    status, reads, writes, rewinds, _ = invoke(harness, "copy", plan, data)
    assert (status, reads, writes, rewinds) == (-1, 0, 0, 0)


def plan_snapshot():
    value = snapshot()
    originals = (
        image(),
        image(),
        CONFIG,
        b'<config><cloud><a key="cloudregisterurl" value="https://10.0.0.1:8443/nest/entry"/></cloud><a key="uploadlogs" value="0"/></config>',
    )
    return replace(
        value, records=tuple(replace(r, data=d) for r, d in zip(value.records, originals))
    )


def test_offline_plan_is_deterministic_and_requires_full_backup_custody(tmp_path):
    tmp_path.chmod(0o700)
    value = plan_snapshot()
    network_backup.preserve(tmp_path / "backup", value)
    args = (value, tmp_path / "backup", "https://10.0.0.1:8443", "https://10.0.0.12:8443")
    assert network_plan.prepare(tmp_path / "first", *args)["installed"] is False
    network_plan.prepare(tmp_path / "repro", *args)
    for p in (tmp_path / "first").iterdir():
        assert p.read_bytes() == (tmp_path / "repro" / p.name).read_bytes()
        assert p.stat().st_mode & 0o777 == 0o600
    (tmp_path / "backup/0.original").write_bytes(b"bad")
    with pytest.raises(ValueError):
        network_plan.prepare(tmp_path / "refused", *args)
    assert not (tmp_path / "refused").exists()


@pytest.fixture(scope="module")
def transaction_harness(tmp_path_factory):
    if shutil.which("clang") is None:
        pytest.skip("Clang needed for scoped transaction sanitizer checks")
    path = tmp_path_factory.mktemp("network-transaction") / "transaction"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DHEARTH_HOST_LAB",
            "-DHEARTH_NETWORK_ADAPTER",
            "-DHEARTH_CLEAN_FIXTURE",
            "-fsanitize=address,undefined",
            "-Wl,--wrap=write,--wrap=read,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            "tests/network_transaction_harness.c",
            "firmware/file_install/posix.c",
            "firmware/file_install/transaction.c",
            "-o",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.mark.parametrize("scenario", range(20))
def test_scoped_large_file_transaction_restore_and_faults(transaction_harness, tmp_path, scenario):
    result = subprocess.run(
        [str(transaction_harness), str(scenario), str(tmp_path)],
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert not result.stdout and not result.stderr
    assert not list(tmp_path.iterdir())


def test_exact_memory_selftest_source_under_host_sanitizers(tmp_path):
    if shutil.which("clang") is None:
        pytest.skip("Clang needed for RAM selftest source check")
    output = tmp_path / "ram-selftest"
    subprocess.run(
        [
            "clang",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fsanitize=address,undefined",
            "tests/network_ram_harness.c",
            "firmware/network_update/ram.c",
            "firmware/network_update/hash.c",
            "firmware/network_update/stream.c",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    result = subprocess.run([str(output)], check=True, capture_output=True, timeout=10)
    assert not result.stdout and not result.stderr
