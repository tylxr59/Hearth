"""Independent custody validation of a protected installer acquisition."""

import hashlib
import json
import stat

from firmware.acquisition import codec
from firmware.acquisition.run import collected_files
from provisioning import file_backup, network_backup
from tools.elf_review import private_path


def read(path, limit):
    path = private_path(path)
    meta = path.stat()
    if (
        not stat.S_ISREG(meta.st_mode)
        or stat.S_IMODE(meta.st_mode) != 0o600
        or meta.st_size > limit
    ):
        raise ValueError("bounded owner-only acquired file required")
    data = path.read_bytes()
    if len(data) != meta.st_size:
        raise ValueError("acquisition file changed while reading")
    return data


def verify(root):
    root = private_path(root)
    if not root.is_dir() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise ValueError("owner-only acquisition directory required")
    frame = read(root / "capture.bin", codec.MAX_PAYLOAD + 56)
    if len(frame) < 48:
        raise ValueError("complete acquisition snapshot required")
    session = frame[8:40]
    decoder = codec.Decoder(session, lambda *_: None)
    for name in (
        "capture.bin",
        "network-capture.bin",
        *[f"group-{i}.bin" for i in range(4)],
        "completion.bin",
    ):
        data = read(root / name, codec.LIMIT + 60)
        for at in range(0, len(data), 65536):
            decoder.feed(data[at : at + 65536])
    expected = collected_files(decoder)
    record = json.loads(read(root / "extraction.json", 1024 * 1024))
    if (
        set(record) != {"format", "files", "source", "symlinks_created", "executables_run_on_host"}
        or record["format"] != "hearth-private-installer-inputs-v1"
        or record["symlinks_created"] is not False
        or record["executables_run_on_host"] is not False
        or record["source"]
        != "protected root0/user-config view; native active root separately observed"
    ):
        raise ValueError("original acquisition metadata required")
    rows = []
    for name, (data, mode, owner, group, source) in sorted(expected.items()):
        if read(root / "corpus" / name, codec.FILE_LIMIT) != data:
            raise ValueError("private corpus differs from captured frame")
        rows.append(
            {
                "path": name,
                "mode": mode,
                "owner": owner,
                "group": group,
                "source": source,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    if record["files"] != rows:
        raise ValueError("acquisition index differs from original frames")
    actual = set()
    for path in (root / "corpus").rglob("*"):
        path = private_path(path)
        meta = path.stat()
        if stat.S_ISDIR(meta.st_mode):
            if stat.S_IMODE(meta.st_mode) != 0o700:
                raise ValueError("owner-only corpus directories required")
        elif stat.S_ISREG(meta.st_mode):
            actual.add(path.relative_to(root / "corpus").as_posix())
        else:
            raise ValueError("regular corpus data only")
    if actual != set(expected):
        raise ValueError("unexpected private corpus file")
    plan = hashlib.sha256(
        b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
    ).digest()
    file_backup.verify(
        root / "backup", decoder.snapshot, session=session, plan=plan, native_root="root0"
    )
    network_backup.verify(root / "network-backup", decoder.network)
    return decoder, record
