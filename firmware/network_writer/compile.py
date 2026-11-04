"""Cross-build original scoped network actions; vendor originals are DATA only."""

from pathlib import Path

from firmware.file_writer.compile import IMPORTS
from firmware.network_probe.profile import pinned_plan
from firmware.network_writer.kernel import binding
from firmware.tls_probe.compile import run

ROOT = Path(__file__).resolve().parents[2]
IMPORT_SET = set(IMPORTS) | {"strstr", "memcpy", "malloc", "free", "mmap", "munmap", "mprotect"}


def compile_helpers(
    output,
    plan,
    backup,
    pin,
    *,
    preflight_only=False,
    shared_archive=None,
    capacity_reserve=0,
    sequence_child=False,
):
    if type(sequence_child) is not bool:
        raise ValueError("explicit child-action purpose required")
    if type(preflight_only) is not bool:
        raise ValueError("explicit preflight-only mode required")
    from installer.capacity import checked_reserve

    checked_reserve(capacity_reserve, preflight_only)
    output = Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / "build"):
        raise ValueError("fresh literal build path required")
    bound = pinned_plan(plan, backup, pin)
    target_count = bound["target_count"]
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "plan.h").write_bytes(bound["header"])
    (output / "binding.h").write_bytes(binding(plan, backup, pin))
    (output / "session.h").write_text("static const unsigned char hearth_session[32]={0};\n")
    if shared_archive is not None:
        from firmware.network_writer.shared import checked

        if target_count != 3:
            raise ValueError("shared originals are cleanup3-only")
        shared = checked(shared_archive, backup, bound["plan"])
        (output / "shared-plan.h").write_bytes(shared["header"])
    common = [
        "clang",
        "--target=arm-linux-gnueabihf",
        "-marm",
        "-march=armv7-a",
        "-mfpu=vfpv3-d16",
        "-mfloat-abi=hard",
        "-Os",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fno-builtin",
        "-ffreestanding",
        "-fno-stack-protector",
        "-fomit-frame-pointer",
        "-fuse-ld=lld",
        "-nostdlib",
        "-Wl,--build-id=none,-z,noexecstack",
        "-I" + str(output),
        f"-DHEARTH_NETWORK_TARGET_COUNT={target_count}",
        *(["-DHEARTH_NETWORK_SHARED_BACKUPS"] if shared_archive is not None else []),
        *(["-DHEARTH_NETWORK_VARIABLE_TIME"] if bound.get("custom_time") else []),
    ]
    stub = output / "libc.stub.c"
    stub.write_text("\n".join(f"long {name}(void) {{ return 0; }}" for name in sorted(IMPORT_SET)))
    run(
        common
        + ["-shared", "-fPIC", "-Wl,-soname,libc.so.6", str(stub), "-o", str(output / "libc.so.6")]
    )
    entry = [
        "-no-pie",
        "-Wl,-e,_start,--dynamic-linker=/lib/ld-linux-armhf.so.3",
        str(ROOT / "firmware/tls_probe/start.S"),
    ]
    run(
        common
        + entry
        + [
            "-DHEARTH_RAM_LAB",
            "-DHEARTH_NETWORK_ADAPTER",
            "-Wl,--wrap=write,--wrap=read,--wrap=fsync,--wrap=renameat,--wrap=fchmod,--wrap=fchown",
            *[
                str(ROOT / n)
                for n in (
                    "tests/network_transaction_harness.c",
                    "firmware/file_install/posix.c",
                    "firmware/file_install/transaction.c",
                )
            ],
            *([str(ROOT / "firmware/network_update/hash.c")] if shared_archive is not None else []),
            str(output / "libc.so.6"),
            "-o",
            str(output / "network-transaction"),
        ]
    )
    for action in (1, 2):
        run(
            common
            + entry
            + [
                "-DHEARTH_NETWORK_ADAPTER",
                *(["-DHEARTH_SEQUENCE_CHILD"] if sequence_child else []),
                *(["-DHEARTH_PREFLIGHT_ONLY=1"] if preflight_only else []),
                f"-DHEARTH_CAPACITY_RESERVE={capacity_reserve}U",
                f"-DHEARTH_FILE_MASK={(1 << target_count) - 1}U",
                f"-DHEARTH_FILE_ACTION={action}",
                *[
                    str(ROOT / n)
                    for n in (
                        "firmware/network_writer/action.c",
                        "firmware/network_writer/data.c",
                        "firmware/network_writer/adapter.c",
                        "firmware/network_update/hash.c",
                        "firmware/network_update/stream.c",
                        "firmware/file_writer/lifecycle.c",
                        "firmware/file_install/transaction.c",
                    )
                ],
                str(output / "libc.so.6"),
                "-o",
                str(output / f"action-{action}"),
            ]
        )
        run(
            common
            + [
                "-static",
                "-Wl,-e,_start",
                f"-DHEARTH_WRITER_ACTION={action}",
                *[
                    str(ROOT / n)
                    for n in (
                        "firmware/network_probe/init.c",
                        "firmware/network_update/ram.c",
                        "firmware/network_update/hash.c",
                        "firmware/network_update/stream.c",
                    )
                ],
                "-o",
                str(output / f"init-{action}"),
            ]
        )
    for p in output.iterdir():
        if p.is_file():
            p.chmod(0o600)
    return output
