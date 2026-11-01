"""Cross-build original scoped network actions; vendor originals are DATA only."""

from pathlib import Path

from firmware.file_writer.compile import IMPORTS
from firmware.network_probe.profile import pinned_plan
from firmware.network_writer.kernel import binding
from firmware.tls_probe.compile import run

ROOT = Path(__file__).resolve().parents[2]
IMPORT_SET = set(IMPORTS) | {"strstr", "memcpy", "malloc", "free", "mmap", "munmap", "mprotect"}


def compile_helpers(output, plan, backup, pin):
    output = Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / "build"):
        raise ValueError("fresh literal build path required")
    bound = pinned_plan(plan, backup, pin)
    output.mkdir(mode=0o700, exist_ok=False)
    (output / "plan.h").write_bytes(bound["header"])
    (output / "binding.h").write_bytes(binding(plan, backup, pin))
    (output / "session.h").write_text("static const unsigned char hearth_session[32]={0};\n")
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
                "-DHEARTH_FILE_MASK=15U",
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
