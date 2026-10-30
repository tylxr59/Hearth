"""Explicit Docker/Podman selection for opt-in loopback laboratory tests."""

import os

ENGINE = os.environ.get("HEARTH_CONTAINER_ENGINE", "docker")
if ENGINE not in ("docker", "podman"):
    raise ValueError("HEARTH_CONTAINER_ENGINE must be docker or podman")


def command(args):
    args = list(args)
    if len(args) < 2 or args[0] != ENGINE:
        return args
    if ENGINE == "podman":
        if args[1] == "run" and "--user" in args and os.getuid() != 0:
            # Preserve the invoking uid for private bind-mounted test credentials.
            # Default-image UID assertions deliberately omit --user and keep the
            # normal namespace mapping. Never loosen fixture file permissions.
            args.insert(2, "--userns=keep-id")
        args = ["docker.io/library/" + a if a.startswith("eclipse-mosquitto:") else a for a in args]
    return args
