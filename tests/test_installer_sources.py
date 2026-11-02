"""Public source integrity and build isolation; fixtures do not download/run USB."""

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from installer import build, sources


@pytest.fixture
def source_root(tmp_path, monkeypatch):
    (tmp_path / "build").mkdir()
    monkeypatch.setattr(sources, "ROOT", tmp_path)
    return tmp_path


def test_source_cache_cannot_escape_build_or_follow_symlink(source_root):
    assert sources.build_path(source_root / "build/fresh") == source_root / "build/fresh"
    for invalid in (
        source_root / "private/owner",
        source_root / "build",
        source_root / "build/../outside",
    ):
        with pytest.raises(ValueError):
            sources.build_path(invalid)
    (source_root / "build/link").symlink_to(source_root, target_is_directory=True)
    with pytest.raises(ValueError):
        sources.build_path(source_root / "build/link/new")


@pytest.mark.parametrize("fault", (None, "digest", "length", "oversize"))
def test_compiler_download_requires_exact_bounded_public_bytes(tmp_path, monkeypatch, fault):
    data = b"synthetic public compiler archive"
    expected = data
    if fault == "digest":
        data = b"x" * len(data)
    elif fault == "length":
        data = data[:-1]
    elif fault == "oversize":
        data += b"extra"
    opened = []

    def open_public(url, timeout):
        opened.append((url, timeout))
        return io.BytesIO(data)

    monkeypatch.setattr(
        sources.urllib.request, "build_opener", lambda _: SimpleNamespace(open=open_public)
    )
    destination = tmp_path / "compiler"
    record = {
        "url": "https://example.test/compiler",
        "bytes": len(expected),
        "sha256": hashlib.sha256(expected).hexdigest(),
    }
    if fault:
        with pytest.raises(ValueError):
            sources.compiler(destination, record)
    else:
        sources.compiler(destination, record)
        assert destination.read_bytes() == expected
    assert len(opened) == 1


def test_public_download_redirect_cannot_downgrade_tls():
    with pytest.raises(ValueError, match="HTTPS"):
        sources.HttpsRedirect().redirect_request(
            None, None, 302, "", {}, "http://example.test/archive"
        )


def test_source_pin_mismatch_refuses_before_git_or_compiler(source_root, monkeypatch):
    cache = source_root / "build/cache"
    cache.mkdir()
    (cache / "sources.json").write_text("{}")
    monkeypatch.setattr(sources, "git", lambda *_: pytest.fail("no git after mismatched pins"))
    with pytest.raises(ValueError, match="pin record"):
        sources.verify(cache)


def test_fetch_is_fresh_only_and_records_no_false_success(source_root, monkeypatch):
    cache = source_root / "build/cache"
    cache.mkdir()
    monkeypatch.setattr(sources, "git", lambda *_: pytest.fail("no git for existing cache"))
    with pytest.raises(FileExistsError):
        sources.fetch(cache)
    assert not (cache / "sources.json").exists()


def test_container_build_has_only_public_work_mount_and_no_network_or_privileges():
    args = build.container("podman", build.IMAGE, Path("/public/build/reader"))
    assert "--network=none" in args and "--cap-drop=all" in args
    assert "--security-opt=no-new-privileges" in args
    assert args.count("-v") == 1 and args[args.index("-v") + 1] == "/public/build/reader:/work:Z"
    assert not any(
        x.startswith(("--device", "--privileged", "--pid=host", "--network=host")) for x in args
    )
    assert args[-1] == build.IMAGE


def test_firmware_build_refuses_rootful_runtime_before_any_staging(monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _: "/usr/bin/podman")
    monkeypatch.setattr(
        build.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            stdout=json.dumps({"host": {"security": {"rootless": False}}}).encode()
        ),
    )
    monkeypatch.setattr(
        sources, "verify", lambda _: pytest.fail("must refuse before source/build access")
    )
    with pytest.raises(ValueError, match="rootless"):
        build.build("unused", "unused", "unused")


def test_git_fetch_disables_prompts_and_hooks(monkeypatch, tmp_path):
    calls = []

    def process(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(stdout=b"fixture")

    monkeypatch.setattr(sources.subprocess, "run", process)
    assert sources.git(tmp_path, "fetch", "--depth=1", "origin", "fixed") == b"fixture"
    argv, kwargs = calls[0]
    assert "core.hooksPath=/dev/null" in argv and "protocol.file.allow=never" in argv
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0" and kwargs["timeout"] == 300
