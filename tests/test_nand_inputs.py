"""Offline NAND input reconstruction: synthetic JFFS2 only, no device access."""

import stat
import struct

import pytest

from firmware.acquisition import codec
from installer import nand_inputs as n
from installer.archive_discovery import crc
from provisioning import file_backup, network_backup
from tests.test_archive_discovery import dirent, inode, node


def entry(
    ino, data=b"", *, mode=stat.S_IFREG | 0o600, version=1, offset=0, size=None, compression=0
):
    raw = bytearray(inode(ino, data, codec=compression, version=version))
    struct.pack_into("<I", raw, 20, mode)
    struct.pack_into("<I", raw, 28, len(data) if size is None else size)
    struct.pack_into("<I", raw, 44, offset)
    struct.pack_into("<I", raw, 64, crc(raw[:60]))
    return bytes(raw)


def filesystem(files):
    rows = [entry(1, mode=stat.S_IFDIR | 0o755)]
    parents, next_ino = {"": 1}, 2
    for path, data in files.items():
        parent = ""
        parts = path.split("/")
        for name in parts[:-1]:
            current = parent + "/" + name
            if current not in parents:
                parents[current] = next_ino
                rows.extend(
                    (
                        dirent(parents[parent], name.encode(), next_ino),
                        entry(next_ino, mode=stat.S_IFDIR | 0o755),
                    )
                )
                next_ino += 1
            parent = current
        rows.extend((dirent(parents[parent], parts[-1].encode(), next_ino), entry(next_ino, data)))
        next_ino += 1
    return b"".join(rows)


def test_frames_decode_and_preserve_exact_metadata_without_claiming_live_space():
    files = {
        path: path.encode() for i, path in enumerate(file_backup.TARGETS) if i not in (4, 5, 7)
    }
    files.update({path: path.encode() for path in network_backup.TARGETS})
    files.update({prefix + "/library": b"opaque bytes" for prefix in codec.GROUPS})
    root = n.Filesystem(filesystem(files))
    user = n.Filesystem(filesystem({"settings.config": b"settings"}))
    frames = n.frames(root, user, b"s" * 32)
    decoder = codec.Decoder(b"s" * 32, lambda *_: None)
    for name in n.NAMES:
        decoder.feed(frames[name])
    assert decoder.complete
    assert decoder.snapshot[7].data == b"settings"
    assert not decoder.snapshot[4].existed and not decoder.snapshot[5].existed
    assert decoder.network.filesystem[2:4] == (0, 0)
    assert decoder.network.records[0].data == network_backup.TARGETS[0].encode()
    assert decoder.snapshot[8].data == decoder.network.records[3].data


def test_versioned_overwrites_truncation_and_metadata():
    data = (
        entry(2, b"old bytes")
        + entry(2, b"new", version=2, size=5)
        + entry(2, b"!", version=3, offset=4, size=5)
    )
    # A complete older fragment supplies the byte not overwritten by newer nodes.
    assert n.Filesystem(data).contents(2, 100)[0] == b"new !"


@pytest.mark.parametrize("fault", ("crc", "gap", "codec", "symlink", "xattr", "ambiguous"))
def test_unsafe_or_incomplete_originals_refuse(fault):
    data = entry(2, b"original")
    if fault == "crc":
        damaged = bytearray(entry(2, b"new", version=2))
        damaged[68] ^= 1
        data += damaged
    elif fault == "gap":
        data = entry(2, b"x", offset=1, size=2)
    elif fault == "codec":
        data = entry(2, b"x", compression=7)
    elif fault == "symlink":
        data = entry(2, b"elsewhere", mode=stat.S_IFLNK | 0o777)
    elif fault == "xattr":
        data += node(0xE009, struct.pack("<4I", 2, 1, 1, 0))
    else:
        data += entry(2, b"different")
    with pytest.raises(ValueError):
        n.Filesystem(data).contents(2, 100)


def test_paths_never_follow_links_and_only_optional_leaf_may_be_absent():
    view = n.Filesystem(filesystem({"dir/original": b"bytes"}))
    assert view.original("dir/missing", 4, 100, absent=True).existed is False
    with pytest.raises(ValueError):
        view.lookup("missing/original", absent=True)
    with pytest.raises(ValueError):
        view.lookup("dir/../original")


def test_rtime_exact_expansion_and_truncation():
    assert n.rtime(b"a\0b\0a\2", 5) == b"ababa"
    for raw, size in ((b"a", 1), (b"a\2", 2), (b"a\0x", 1)):
        with pytest.raises(ValueError):
            n.rtime(raw, size)


def test_archive_provenance_is_recomputed_and_tampering_refuses(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    root = tmp_path / "acquisition"
    root.mkdir(mode=0o700)
    quality = tmp_path / "nand/analysis"
    quality.mkdir(parents=True, mode=0o700)
    (quality / "quality.json").write_bytes(b"{}")
    (quality / "quality.json").chmod(0o600)
    monkeypatch.setattr(n, "private_path", lambda p: p)
    from firmware.acquisition import custody

    monkeypatch.setattr(custody, "private_path", lambda p: p)
    token = b"s" * 32
    expected = {name: b"expected" for name in n.NAMES}
    monkeypatch.setattr(n, "from_archive", lambda session, key: expected if key == token else {})
    for name, data in expected.items():
        n.save(root, name, data)
    n.save(
        root,
        "nand-inputs.json",
        n.encode(
            {
                "format": n.FORMAT,
                "session": token.hex(),
                "quality_sha256": n.hashlib.sha256(b"{}").hexdigest(),
                "live_filesystem_statistics": False,
            }
        ),
    )
    assert n.verify(root)["live_filesystem_statistics"] is False
    (root / "capture.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        n.verify(root)


def test_implicit_root_and_passive_library_group_metadata():
    raw = bytearray(entry(2, b"library"))
    struct.pack_into("<H", raw, 26, 4)
    struct.pack_into("<I", raw, 64, crc(raw[:60]))
    view = n.Filesystem(
        dirent(1, b"lib", 3) + entry(3, mode=stat.S_IFDIR | 0o755) + dirent(3, b"library", 2) + raw
    )
    assert view.lookup("lib/library") == 2
    assert view.contents(2, 100)[3] == 4
    with pytest.raises(ValueError, match="root-owned"):
        view.original("lib/library", 0, 100)
