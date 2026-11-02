import json
import shutil
import subprocess

import pytest

from firmware.acquisition import codec, run
from firmware.file_writer.run import save
from installer import corpus
from tests.test_acquisition import SESSION, decoded, group_frame, payload


@pytest.fixture
def acquisition(tmp_path, monkeypatch):
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    root = tmp_path / "acquisition"
    root.mkdir(mode=0o700)
    decoder, frames = decoded()
    for name, data in frames.items():
        save(root, name, data)
    run.preserve_inputs(root, decoder)
    return root


def test_private_input_check_reconstructs_frames_and_both_custody_receipts(acquisition):
    decoder, record = corpus.verify(acquisition)
    assert decoder.complete and len(record["files"]) == 14
    with pytest.raises(ValueError, match="unresolved"):
        corpus.inspect(acquisition)  # Arbitrary fixture bytes are not native libraries.


@pytest.mark.parametrize(
    "fault",
    ("data", "index", "backup", "extra", "mode", "directory", "symlink", "crc", "completion"),
)
def test_kit_input_check_refuses_changed_private_evidence(acquisition, fault):
    path = acquisition / "corpus/lib/file"
    if fault == "data":
        path.write_bytes(b"changed")
    elif fault == "index":
        index = acquisition / "extraction.json"
        record = json.loads(index.read_bytes())
        record["files"][0]["sha256"] = "0" * 64
        index.write_text(json.dumps(record))
    elif fault == "backup":
        (acquisition / "backup/0.original").write_bytes(b"changed")
    elif fault == "extra":
        save(acquisition / "corpus", "unexpected", b"extra")
    elif fault == "mode":
        path.chmod(0o644)
    elif fault == "directory":
        path.parent.chmod(0o755)
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(acquisition / "capture.bin")
    elif fault == "crc":
        path = acquisition / "group-0.bin"
        data = bytearray(path.read_bytes())
        data[48] ^= 1
        path.write_bytes(data)
    else:
        (acquisition / "completion.bin").unlink()
    with pytest.raises((ValueError, OSError)):
        corpus.verify(acquisition)


def test_soname_resolver_needs_no_symlinks_or_native_execution(tmp_path, monkeypatch):
    if not all(shutil.which(name) for name in ("clang", "ld.lld", "readelf")):
        pytest.skip("Clang/LLD/readelf required for original synthetic ARM DSO fixtures")
    from tools import elf_review

    monkeypatch.setattr(elf_review, "PRIVATE", tmp_path)
    build = tmp_path / "synthetic"
    build.mkdir()
    source = build / "stub.c"
    source.write_text("int hearth_synthetic_export(void) { return 0; }\n")
    rows = []
    compiled = {}
    for soname in (
        "ld-linux-armhf.so.3",
        "libc.so.6",
        "libdl.so.2",
        "libcurl.so.4",
        "libnlwebservice.so",
    ):
        output = build / (soname + ".synthetic")
        # Compile only original fixture code, never a proprietary input. These
        # shared objects are parsed, not loaded or invoked on the host.
        dependencies = {
            "ld-linux-armhf.so.3": (),
            "libc.so.6": ("ld-linux-armhf.so.3",),
            "libdl.so.2": ("libc.so.6",),
            "libcurl.so.4": ("libc.so.6",),
            "libnlwebservice.so": ("libcurl.so.4", "libdl.so.2"),
        }[soname]
        subprocess.run(
            [
                "clang",
                "--target=arm-linux-gnueabihf",
                "-fuse-ld=lld",
                "-nostdlib",
                "-shared",
                "-fPIC",
                "-Wl,-soname," + soname,
                str(source),
                "-Wl,--no-as-needed",
                *[str(compiled[name]) for name in dependencies],
                "-o",
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        compiled[soname] = output
        rows.append((output.name.encode(), output.read_bytes(), 0o100755))
    _, frames = decoded()
    frames["group-0.bin"] = group_frame(0, payload(rows))
    root = tmp_path / "inputs"
    root.mkdir(mode=0o700)
    decoder = codec.Decoder(SESSION, lambda name, data: save(root, name, data))
    for frame in frames.values():
        for at in range(0, len(frame), 65536):
            decoder.feed(frame[at : at + 65536])
    run.preserve_inputs(root, decoder)
    result = corpus.inspect(root)
    assert result["native_libraries"] == 5
    assert result["native_code_executed"] is False and not result["install_kit_built"]
    assert not any(path.is_symlink() for path in (root / "corpus").rglob("*"))
    from firmware.file_writer.profile import native_libraries

    pair = native_libraries(root)
    assert {row[0] for row in pair} == {"lib/libc.so.6", "lib/ld-linux-armhf.so.3"}
    assert {row[0]: row[1] & 0o777 for row in pair} == {
        "lib/libc.so.6": 0o444,
        "lib/ld-linux-armhf.so.3": 0o555,
    }
    assert all(row[2] == 0 and row[4:] == (0, 0) for row in pair)
