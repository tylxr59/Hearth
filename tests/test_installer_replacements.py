"""Synthetic stock custody, no device access or vendor native bytes."""

import hashlib
import json
from dataclasses import replace

import pytest

from firmware.acquisition import codec, run
from firmware.file_writer.run import encode, save
from installer import replacements
from provisioning import file_capsule, network_plan
from tests.conftest import SERIAL
from tests.test_acquisition import SESSION, group_frame, payload
from tests.test_file_snapshot_profile import frame as snapshot_frame
from tests.test_native_settings import TOKEN, settings
from tests.test_native_startup import original as startup
from tests.test_native_tls_candidate import synthetic as tls_library
from tests.test_network_snapshot import frame as network_frame
from tests.test_network_stream import plan_snapshot


@pytest.fixture
def stock(tmp_path, monkeypatch, request):
    from firmware.file_snapshot.run import decode
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    monkeypatch.setattr(replacements, "build_path", lambda path: path)
    tmp_path.chmod(0o700)
    session = tmp_path / "session"
    session.mkdir(mode=0o700)
    acquired = session / "acquisition"
    acquired.mkdir(mode=0o700)
    bundle = {"serial": SERIAL, "credential": TOKEN, "origin": "https://10.0.0.12:8443"}
    raw = b"synthetic commissioning fixture"
    monkeypatch.setattr(
        replacements,
        "read_bundle",
        lambda _, **kw: (bundle, b"public CA fixture", b"public CRL fixture"),
    )
    records = list(decode(snapshot_frame(), SESSION))
    network = plan_snapshot()
    values = {
        0: tls_library(),
        3: b"# original\nserver time.nest.com\n",
        6: startup(),
        7: settings(),
        8: network.records[3].data,
    }
    for index, data in values.items():
        records[index] = replace(records[index], data=data)
    existing = getattr(request, "param", None)
    for index, mode in ((4, 0o444), (5, 0o750)):
        if existing in (index, "both"):
            records[index] = replace(
                records[index], existed=True, mode=mode, data=b"existing Hearth fixture"
            )
    network = replace(network, records=network.records[:3] + (replace(records[8], target=3),))
    decoder = codec.Decoder(SESSION, lambda name, data: save(acquired, name, data))
    library_rows = [(b"libnlwebservice.so", records[0].data, 0o100644)]
    app_rows = [(b"nlclient", network.records[0].data, 0o100644)]
    if records[4].existed:
        library_rows.append((b"libhearth-settings-compat.so", records[4].data, 0o100444))
    if records[5].existed:
        app_rows.append((b"hearth-nlclient", records[5].data, 0o100750))
    frames = (
        snapshot_frame(tuple(records)),
        network_frame(network),
        group_frame(0),
        group_frame(1),
        group_frame(2, payload(library_rows)),
        group_frame(3, payload(app_rows)),
        codec.DONE,
    )
    for data in frames:
        decoder.feed(data)
    run.preserve_inputs(acquired, decoder)
    identity = {
        "serial": SERIAL,
        "model": "Display-2.6",
        "software": "5.9.4-5",
        "partition": "primary",
    }
    save(session, "commissioning.zip", raw)
    save(session, "identity.json", encode(identity))
    save(
        acquired,
        "intake-binding.json",
        encode(
            {
                "format": "hearth-acquisition-session-v1",
                "identity": identity,
                "bundle_sha256": hashlib.sha256(raw).hexdigest(),
                "session": SESSION.hex(),
            }
        ),
    )
    compiled = []

    def compile_shim(path, **kwargs):
        compiled.append(kwargs)
        path.mkdir(mode=0o700)

    monkeypatch.setattr(replacements, "compile_library", compile_shim)
    monkeypatch.setattr(replacements, "read_build", lambda *_: b"original synthetic shim DATA")
    return session, tmp_path / "build", tmp_path / "kit", compiled


def test_preparation_binds_nine_and_three_disjoint_scopes_and_original_custody(stock):
    session, build, output, compiled = stock
    result = replacements.prepare(session, build, output)
    assert result["disjoint"] is True and not result["write_profiles_ready"]
    assert not result["device_executed"] and not result["flash_writes"]
    assert compiled == [{"legacy_linker": True, "builder_image": replacements.IMAGE}]
    core = json.loads((output / "commissioning-pin.json").read_bytes())
    file_capsule.check(output / "commissioning", expected_plan=bytes.fromhex(core["plan"]))
    cleanup = json.loads((output / "cleanup-pin.json").read_bytes())
    bound = network_plan.check(
        output / "cleanup", session / "acquisition/network-backup", bytes.fromhex(cleanup["plan"])
    )
    assert bound["target_count"] == 3 and not (output / "cleanup/3.replacement").exists()
    assert (output / "commissioning/7.replacement").read_bytes() != (
        output / "commissioning/backup/7.original"
    ).read_bytes()
    assert b"10.0.0.12:8443/nest/entry" in (output / "commissioning/8.replacement").read_bytes()
    assert b'key="uploadlogs" value="0"' in (output / "commissioning/8.replacement").read_bytes()
    assert (
        (output / "commissioning/3.replacement")
        .read_bytes()
        .endswith(b"server time.nist.gov minpoll 6 maxpoll 10\n")
    )
    for path in output.rglob("*"):
        assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)
    assert replacements.check(output, session) is True


@pytest.mark.parametrize("fault", ("identity", "bundle", "nonce", "binding"))
def test_mismatched_acquisition_identity_or_bundle_refuses_before_compilation(stock, fault):
    session, build, output, compiled = stock
    path = session / "acquisition/intake-binding.json"
    binding = json.loads(path.read_bytes())
    if fault == "identity":
        binding["identity"]["software"] = "other"
    elif fault == "bundle":
        binding["bundle_sha256"] = "0" * 64
    elif fault == "nonce":
        binding["session"] = "0" * 64
    else:
        binding["format"] = "unknown"
    path.write_bytes(encode(binding))
    with pytest.raises(ValueError):
        replacements.prepare(session, build, output)
    assert not compiled and not output.exists() and not build.exists()


def test_existing_preparation_is_never_overwritten(stock):
    session, build, output, compiled = stock
    output.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        replacements.prepare(session, build, output)
    assert not compiled and not build.exists()


@pytest.mark.parametrize("stock", (4, 5, "both"), indirect=True)
def test_stock_installer_refuses_existing_or_partial_hearth_before_compiling(stock):
    session, build, output, compiled = stock
    with pytest.raises(ValueError, match="upgrade/recovery"):
        replacements.prepare(session, build, output)
    assert not compiled and not output.exists() and not build.exists()


@pytest.mark.parametrize("server", ("ntp.example.test", "10.0.0.8"))
def test_custom_time_is_bound_consistently_in_both_phases(stock, server):
    session, build, output, _ = stock
    replacements.prepare(session, build, output, ntp_server=server)
    assert ("server " + server + " minpoll").encode() in (
        output / "commissioning/3.replacement"
    ).read_bytes()
    assert ("FallbackTimeservers=" + server).encode() in (
        output / "cleanup/2.replacement"
    ).read_bytes().replace(b" ", b"")
    assert replacements.check(output, session)
    (output / "time-server.json").write_text(json.dumps({"server": "different.example"}))
    with pytest.raises(ValueError):
        replacements.check(output, session)
