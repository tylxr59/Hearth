"""Prepare only the reviewed native launch argument and a small exec wrapper."""

import re

from backend.validation import Invalid

LAUNCHER = b"""#!/bin/sh
# Hearth: preload only into the native application, after the service launcher.
export LD_PRELOAD=/nestlabs/lib/libhearth-settings-compat.so
exec /nestlabs/sbin/nlclient "$@"
"""
COMMAND = re.compile(
    rb'(?m)^(?P<prefix>[ \t]*\$\{STARTDAEMON\} -q -b -p "\$\{NLCLIENTPIDFILE\}" -a )'
    rb'(?P<argument>"\$\{NLCLIENTAPP\}")'
    rb"(?P<suffix> -- `find_configs \$\{NESTLABSCONFDIR\} \$\{CONFFILENAMES\}`[ \t]*\r?)$"
)


def native_startup(data):
    """Preserve native stop matching and all other script bytes; never execute it."""
    if not isinstance(data, bytes) or len(data) > 65536 or b"\0" in data:
        raise Invalid("bounded native startup script required")
    active = [line.strip() for line in data.splitlines() if not line.lstrip().startswith(b"#")]
    if any(b"LD_PRELOAD" in line or b"hearth-nlclient" in line for line in active):
        raise Invalid("pre-existing preload or Hearth launcher requires review")
    starts = [line for line in active if line.startswith(b"${STARTDAEMON}")]
    matches = list(COMMAND.finditer(data))
    if len(starts) != 1 or len(matches) != 1:
        raise Invalid("exactly one reviewed native start command required")
    match = matches[0]
    return (
        data[: match.start("argument")]
        + b'"/nestlabs/sbin/hearth-nlclient"'
        + data[match.end("argument") :]
    )
