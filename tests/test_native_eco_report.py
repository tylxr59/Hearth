import json

import pytest

from backend import reported_cache
from backend.core import Core
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline


@pytest.mark.parametrize("mode", ["schedule", "manual-eco", "auto-eco"])
def test_observed_eco_mode_is_minimal_cached_and_not_fresh_after_restore(rig, mode):
    n = NativeControls(rig[0])
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {
                        "eco": {"mode": mode, "private_native_metadata": "never-save-marker"}
                    },
                }
            ]
        },
    )
    assert n.eco_mode(SERIAL) == mode
    assert n.state_source(SERIAL, "preset") == "device"
    data = n.snapshot_reported()
    assert data["devices"][SERIAL]["records"]["device"]["values"]["eco"] == {"mode": mode}
    assert "never-save-marker" not in json.dumps(data)
    restored = NativeControls(Core(n.core.registry))
    restored.restore_reported(data)
    assert restored.eco_mode(SERIAL) == mode
    assert restored.state_source(SERIAL, "preset") == "cache"
    assert not restored.core.available(SERIAL) and not restored.intents


@pytest.mark.parametrize("value", [{"mode": "future-unknown"}, {"mode": True}, "manual-eco"])
def test_unknown_actual_eco_mode_is_not_replaced_with_a_guessed_cached_mode(rig, value):
    n = NativeControls(rig[0])
    baseline(n)
    key = f"device.{SERIAL}"
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"eco": {"mode": "manual-eco"}}}]})
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"eco": value}}]})
    assert n.eco_mode(SERIAL) == "unknown"
    assert "eco" not in n.snapshot_reported()["devices"][SERIAL]["records"]["device"]["values"]
    assert not n.intents


def test_cache_refuses_unprojected_eco_metadata(rig):
    n = NativeControls(rig[0])
    baseline(n)
    data = n.snapshot_reported()
    data["devices"][SERIAL]["records"]["device"]["values"]["eco"] = {
        "mode": "schedule",
        "unknown": "must-not-persist",
    }
    with pytest.raises(Invalid):
        reported_cache.encode(data)
