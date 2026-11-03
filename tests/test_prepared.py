import json

import pytest

from installer import prepared
from tests.test_installer import info


@pytest.fixture
def session(tmp_path, monkeypatch):
    from tools import elf_review

    tmp_path.chmod(0o700)
    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    monkeypatch.setattr(prepared, "ROOT", tmp_path)
    folder = tmp_path / "setup-test"
    folder.mkdir(mode=0o700)
    build = tmp_path / "build/setup-test"
    build.mkdir(mode=0o700, parents=True)
    identity = prepared.device_info(info())
    for name, value in {
        "wizard-stopped.json": {"phase": "prepare"},
        "prepare-request.json": {
            "operation": "prepare",
            "session": str(folder),
            "build": str(build),
        },
        "identity.json": identity,
        "wizard-settings.json": {"ntp_server": "time.nist.gov"},
    }.items():
        (folder / name).write_text(json.dumps(value))
    (folder / "commissioning.zip").write_bytes(b"synthetic")
    monkeypatch.setattr(
        prepared, "read_bundle", lambda _: ({"serial": identity["serial"]}, b"ca", b"crl")
    )
    monkeypatch.setattr(prepared.acquisition, "check", lambda _: None)
    monkeypatch.setattr(prepared.nand, "check", lambda _: None)
    monkeypatch.setattr(prepared, "checked_library", lambda _: None)
    monkeypatch.setattr(prepared, "installer_archive", lambda p: p.write_bytes(b"public source"))
    return folder, build


def test_predevice_continuation_keeps_prior_evidence_and_never_repeats(session):
    folder, build = session
    previous = (folder / "wizard-stopped.json").read_bytes()
    assert prepared.load(folder, info()) == (folder, build, "time.nist.gov")
    assert (folder / "wizard-stopped.json").read_bytes() == previous
    assert (folder / "installer-source.zip").read_bytes() == b"public source"
    assert (folder / "installer-source.zip").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        prepared.load(folder, info())


@pytest.mark.parametrize(
    "marker",
    (
        "nand",
        "nand-request.json",
        "nand-reader-executed.json",
        "acquire-request.json",
        "acquisition",
        "kit",
        "reader/execution-started.json",
        "prepare-worker-result.json",
        "installer-source.zip",
    ),
)
def test_any_possible_device_attempt_or_completed_prepare_refuses(session, marker):
    folder, _ = session
    path = folder / marker
    path.parent.mkdir(exist_ok=True)
    path.touch()
    with pytest.raises(ValueError):
        prepared.load(folder, info())
    assert not (folder / "prepared-continuation-started.json").exists()


@pytest.mark.parametrize("fault", ("identity", "phase", "build", "profile"))
def test_bad_identity_scope_or_artifact_never_creates_continuation(session, monkeypatch, fault):
    folder, _ = session
    if fault == "identity":
        (folder / "identity.json").write_text("{}")
    elif fault == "phase":
        (folder / "wizard-stopped.json").write_text('{"phase":"install"}')
    elif fault == "build":
        data = json.loads((folder / "prepare-request.json").read_bytes())
        data["build"] = "/other"
        (folder / "prepare-request.json").write_text(json.dumps(data))
    else:

        def reject(_):
            raise ValueError("artifact changed")

        monkeypatch.setattr(prepared.acquisition, "check", reject)
    with pytest.raises(ValueError):
        prepared.load(folder, info())
    assert not (folder / "prepared-continuation-started.json").exists()
