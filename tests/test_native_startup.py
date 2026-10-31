import pytest

from backend.validation import Invalid
from provisioning.native_startup import LAUNCHER, native_startup


def original():
    return (
        b"#!/bin/sh\nNLCLIENTAPP=${NESTLABSSBINDIR}/${NLCLIENTNAME}\n"
        b"stop_service () { ${STOPDAEMON} -q -x ${NLCLIENTAPP}; }\n"
        b' ${STARTDAEMON} -q -b -p "${NLCLIENTPIDFILE}" -a "${NLCLIENTAPP}" -- '
        b"`find_configs ${NESTLABSCONFDIR} ${CONFFILENAMES}`\n"
    )


def test_only_start_argument_changes_and_stop_identity_is_preserved():
    data = original()
    assert native_startup(data) == data.replace(
        b'-a "${NLCLIENTAPP}"', b'-a "/nestlabs/sbin/hearth-nlclient"'
    )
    assert b"-x ${NLCLIENTAPP}" in native_startup(data)
    assert b"export LD_PRELOAD=" in LAUNCHER
    assert LAUNCHER.endswith(b'exec /nestlabs/sbin/nlclient "$@"\n')


@pytest.mark.parametrize(
    "fault",
    [
        lambda x: x.replace(b" -b ", b" "),
        lambda x: x + x,
        lambda x: x.replace(b' -a "${NLCLIENTAPP}"', b" -a /unknown"),
        lambda x: x.replace(b"#!/bin/sh", b"#!/bin/sh\nexport LD_PRELOAD=/unknown"),
        lambda x: x + b"\n${STARTDAEMON} another-command\n",
        lambda x: x + b"\x00",
        lambda x: b"x" * 65537,
        native_startup,
    ],
)
def test_changed_or_ambiguous_startup_requires_review(fault):
    with pytest.raises(Invalid):
        native_startup(fault(original()))


def test_wrapper_exec_preserves_pid_and_literal_arguments(tmp_path):
    import json
    import os
    import shutil
    import subprocess
    import sys

    if not shutil.which("clang"):
        pytest.skip("Clang required for original trusted host preload fixture")
    source = tmp_path / "fixture.c"
    source.write_text("int hearth_fixture_symbol(void) { return 0; }\n")
    library = tmp_path / "fixture.so"
    subprocess.run(
        ["clang", "-shared", "-fPIC", str(source), "-o", str(library)],
        check=True,
        capture_output=True,
    )
    program = tmp_path / "native-fixture"
    program.write_text(
        "#!" + sys.executable + "\nimport json,os,sys\n"
        "print(json.dumps({'pid':os.getpid(),'args':sys.argv[1:],'preload':os.environ.get('LD_PRELOAD')}))\n"
    )
    program.chmod(0o700)
    wrapper = tmp_path / "wrapper"
    wrapper.write_bytes(
        LAUNCHER.replace(
            b"/nestlabs/lib/libhearth-settings-compat.so", os.fsencode(library)
        ).replace(b"/nestlabs/sbin/nlclient", os.fsencode(program))
    )
    wrapper.chmod(0o700)
    arguments = ["space separated", "$(false); literal", "--config", "synthetic.config"]
    process = subprocess.Popen(
        [str(wrapper), *arguments],
        env={"PATH": "/usr/bin:/bin"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0 and stderr == b""
    observed = json.loads(stdout)
    assert observed == {"pid": process.pid, "args": arguments, "preload": str(library)}
