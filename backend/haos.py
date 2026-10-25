"""HAOS launcher: configuration files stay in the private add-on config directory."""

import sys

from backend.api import main

# Required for TLS container networking; host port is disabled by default.
LISTEN_HOST = "0.0.0.0"  # nosec B104

if __name__ == "__main__":
    sys.argv = [
        "hearth",
        "--registry",
        "/config/registry.json",
        "--host",
        LISTEN_HOST,
        "--port",
        "8443",
        "--cert",
        "/config/tls/server.pem",
        "--key",
        "/config/tls/server.key",
        "--mqtt-config",
        "/config/mqtt.json",
    ]
    main()
