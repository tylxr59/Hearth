import json

import pytest

from backend.haos import arguments
from backend.validation import Invalid


def test_existing_launcher_stays_canonical_without_native_profile(tmp_path):
    args = arguments(tmp_path)
    assert "--native-telemetry" not in args
    assert args[args.index("--mqtt-config") + 1] == str(tmp_path / "mqtt.json")
    assert args[args.index("--key") + 1] == str(tmp_path / "tls/server.key")


def test_private_native_profile_selects_bound_https_origin(tmp_path):
    profile = tmp_path / "native-telemetry.json"
    profile.write_text(json.dumps({"origin": "https://192.168.50.2:8443/"}))
    profile.chmod(0o600)
    args = arguments(tmp_path)
    assert "--native-telemetry" in args
    assert args[args.index("--origin") + 1] == "https://192.168.50.2:8443"


@pytest.mark.parametrize("fault", ["public", "symlink", "oversize", "http", "extra", "duplicate"])
def test_native_launcher_profile_failures_are_closed(tmp_path, fault):
    profile = tmp_path / "native-telemetry.json"
    profile.write_text('{"origin":"https://192.168.50.2:8443"}')
    profile.chmod(0o600)
    if fault == "public":
        profile.chmod(0o644)
    elif fault == "symlink":
        target = tmp_path / "real-profile"
        profile.rename(target)
        profile.symlink_to(target)
    elif fault == "oversize":
        profile.write_text(" " * 4097)
    elif fault == "http":
        profile.write_text('{"origin":"http://192.168.50.2:8443"}')
    elif fault == "extra":
        profile.write_text('{"origin":"https://192.168.50.2:8443","insecure":true}')
    else:
        profile.write_text(
            '{"origin":"https://192.168.50.2:8443","origin":"https://127.0.0.1:8443"}'
        )
    with pytest.raises(Invalid):
        arguments(tmp_path)
