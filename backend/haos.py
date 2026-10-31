"""HAOS launcher: configuration files stay in the private add-on config directory."""

import sys
from pathlib import Path

from backend.api import main
from backend.validation import Invalid, endpoint, loads

# Required for TLS container networking; host port is disabled by default.
LISTEN_HOST = "0.0.0.0"  # nosec B104


def arguments(config=Path("/config")):
    config = Path(config)
    result = [
        "hearth",
        "--registry",
        str(config / "registry.json"),
        "--host",
        LISTEN_HOST,
        "--port",
        "8443",
        "--cert",
        str(config / "tls/server.pem"),
        "--key",
        str(config / "tls/server.key"),
        "--mqtt-config",
        str(config / "mqtt.json"),
    ]
    profile = config / "native-telemetry.json"
    if profile.exists() or profile.is_symlink():
        if (
            profile.is_symlink()
            or not profile.is_file()
            or profile.stat().st_mode & 0o077
            or profile.stat().st_size > 4096
        ):
            raise Invalid("native telemetry profile must be a bounded private file")
        data = loads(profile.read_bytes())
        if not isinstance(data, dict) or set(data) != {"origin"}:
            raise Invalid("native telemetry profile requires only origin")
        result += ["--native-telemetry", "--origin", endpoint(data["origin"])]
    return result


if __name__ == "__main__":
    sys.argv = arguments()
    main()
