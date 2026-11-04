"""One explicitly requested protected acquisition; never installs or retries."""

import argparse
import hashlib
import json
import os
import select
import subprocess  # nosec B404
import time

from firmware.acquisition import codec, profile
from firmware.file_writer.run import encode, save
from firmware.probe.observe import require_native
from firmware.settings_compat_probe.observe import observe
from firmware.tls_probe.package import private_read
from provisioning import file_backup, network_backup
from tools.elf_review import private_path


def collected_files(decoder):
    if not decoder.complete or decoder.snapshot is None or decoder.network is None:
        raise ValueError("complete original acquisition required")
    files = {}
    for row in decoder.files:
        files[row.path] = (row.data, row.mode & 0o7777, row.owner, row.group, "root0")
    for records, targets in (
        (decoder.snapshot, file_backup.TARGETS),
        (decoder.network.records, network_backup.TARGETS),
    ):
        for item, target in zip(records, targets, strict=True):
            name = (
                "media/user-config/settings.config"
                if targets is file_backup.TARGETS and item.target == 7
                else target.lstrip("/")
            )
            if not item.existed:
                if name in files:
                    raise ValueError("absent fixed target appeared in acquired directory")
                continue
            value = (
                item.data,
                item.mode,
                item.owner,
                item.group,
                "user-config" if name == "media/user-config/settings.config" else "root0",
            )
            if name in files and files[name] != value:
                raise ValueError("overlapping acquired file bytes/metadata differ")
            files[name] = value
    return files


def preserve_inputs(output, decoder, *, from_nand=False):
    files = collected_files(decoder)
    root = output / "corpus"
    root.mkdir(mode=0o700)
    index = []
    for name, (data, mode, owner, group, source) in sorted(files.items()):
        path = root / name
        current = root
        for part in path.relative_to(root).parts[:-1]:
            current /= part
            current.mkdir(mode=0o700, exist_ok=True)
        save(path.parent, path.name, data)
        index.append(
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
    collection_plan = hashlib.sha256(
        b"read-only-root0-snapshot-v1\n" + "\n".join(file_backup.TARGETS).encode()
    ).digest()
    file_backup.preserve(
        output / "backup",
        decoder.snapshot,
        session=decoder.session,
        plan=collection_plan,
        native_root="root0",
    )
    file_backup.verify(
        output / "backup",
        decoder.snapshot,
        session=decoder.session,
        plan=collection_plan,
        native_root="root0",
    )
    network_backup.preserve(output / "network-backup", decoder.network)
    network_backup.verify(output / "network-backup", decoder.network)
    save(
        output,
        "extraction.json",
        encode(
            {
                "format": "hearth-private-installer-inputs-v1",
                "files": index,
                "source": (
                    "checked full NAND archive; offline root0/user-config reconstruction"
                    if from_nand
                    else "protected root0/user-config view; native active root separately observed"
                ),
                "symlinks_created": False,
                "executables_run_on_host": False,
            }
        ),
    )
    return {
        "status": "protected-installer-inputs-preserved",
        "fixed_snapshots": 2,
        "library_groups": 4,
        "private_files": len(index),
        "flash_writes": False,
        "native_execution": False,
        "firmware_backup": False,
        "whole_firmware_recovery": "unverified",
    }


def send_session(fd, session):
    at, deadline = 0, time.monotonic() + 5
    while at < len(session) and time.monotonic() < deadline:
        if not select.select([], [fd], [], 0.1)[1]:
            continue
        try:
            count = os.write(fd, session[at:])
        except (BlockingIOError, InterruptedError):
            continue
        if count <= 0:
            raise OSError("acquisition session transfer disconnected")
        at += count
    if at != len(session):
        raise TimeoutError("acquisition start incomplete; no retry")


def receive(fd, deadline, session, output):
    decoder = codec.Decoder(session, lambda name, data: save(output, name, data))
    save(
        output,
        "start-sending.json",
        encode({"session_start_sent_once": True, "operation": "read-only-acquisition"}),
    )
    try:
        send_session(fd, session)
        while time.monotonic() < deadline:
            if not select.select([fd], [], [], 0.2)[0]:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                raise OSError("acquisition USB disconnected")
            decoder.feed(chunk)
            if decoder.complete:
                return preserve_inputs(output, decoder)
        raise TimeoutError("acquisition incomplete; private partial output preserved")
    finally:
        if decoder.failure is not None:
            save(output, "failure.json", encode(decoder.failure))
        if decoder.buffer:
            save(output, "incomplete-frame.bin", bytes(decoder.buffer))


def run(root, output=None, *, execute=False, handoff_from_nand=None):
    root = private_path(root)
    checked = profile.check(root)
    if not execute:
        return checked
    if output is None:
        raise ValueError("fresh private output required")
    output = private_path(output)
    if output.exists() or output.parent.stat().st_mode & 0o077:
        raise ValueError("fresh owner-only acquisition output required")
    if handoff_from_nand is None:
        require_native("1-1")
    else:
        from installer.nand_backup import require_handoff

        require_handoff(handoff_from_nand, output.parent)
    record = json.loads(private_read(root / "profile.json", 65536))
    session = bytes.fromhex(record["session"])
    output.mkdir(mode=0o700)
    save(
        root,
        "execution-started.json",
        encode(
            {"output": str(output), "once": True, "operation": "read-only-installer-acquisition"}
        ),
    )
    save(
        output,
        "execution.json",
        encode(
            {
                "profile": str(root),
                "profile_sha256": hashlib.sha256(
                    private_read(root / "profile.json", 65536)
                ).hexdigest(),
                "session": record["session"],
                "flash_writes": False,
                "library_scope": list(codec.GROUPS),
                **(
                    {"handoff_from_nand": str(private_path(handoff_from_nand))}
                    if handoff_from_nand is not None
                    else {}
                ),
            }
        ),
    )
    print(
        "PROTECTED READ-ONLY INSTALLER ACQUISITION: two fixed snapshots and four library/executable directories. No native execution or flash writer. Keep display detached from base and on USB.",
        flush=True,
    )
    print(
        "Waiting up to90 seconds for the owner-timed ROM restart; no automatic retry.", flush=True
    )
    a = root / "artifacts"
    try:
        subprocess.run(
            [
                str(a / "omap_loader"),
                "-f",
                str(a / "x-load-gen2.bin"),
                "-f",
                str(a / "u-boot.bin"),
                "-a",
                "0x80100000",
                "-f",
                str(a / "uImage"),
                "-a",
                "0x80a00000",
                "-j",
                "0x80100000",
            ],
            check=True,
            timeout=90,
        )  # nosec B603

        def capture(fd, deadline, _capture):
            return receive(fd, deadline, session, output)

        result = observe("1-1", 180, receive_fn=capture)
        save(output, "observed.json", encode(result))
        return result
    finally:
        save(output, "finished.json", encode({"host_command_exited": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--execute-read-only-installer-acquisition", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(
                    args.profile, args.output, execute=args.execute_read_only_installer_acquisition
                ),
                indent=2,
            )
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(
            1,
            f"Protected acquisition incomplete ({type(exc).__name__}). Private evidence preserved; no automatic retry. After command exit, manually restart to native startup.\n",
        )
