import json

import pytest

from backend.core import Core
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL


def report(native, value, **metadata):
    return native.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"shared.{SERIAL}",
                    "value": {"current_temperature": value},
                    **metadata,
                }
            ]
        },
    )


def test_temperature_diagnostics_distinguish_missing_accepted_and_refused_reports(rig):
    core, _, _, now = rig
    native = NativeControls(core)
    field = "shared.current_temperature"
    assert native.field_report_view(SERIAL)[field] == {
        "source": "unknown",
        "received": 0,
        "accepted": 0,
        "last_received_age": None,
        "last_accepted_age": None,
    }
    report(native, 24.5)
    now[0] += 10
    # Conditional refusals aren't rejections; the old value remains reported.
    report(native, 20.5, if_object_revision=0)
    assert core.states[SERIAL]["temperature"] == 24.5
    assert native.field_report_view(SERIAL)[field] == {
        "source": "device",
        "received": 2,
        "accepted": 1,
        "last_received_age": 0,
        "last_accepted_age": 10,
    }
    view = json.dumps(native.field_report_view(SERIAL))
    assert "24.5" not in view and "20.5" not in view and SERIAL not in view
    report(native, 20.5)
    assert core.states[SERIAL]["temperature"] == 20.5
    assert native.field_report_view(SERIAL)[field]["accepted"] == 2


def test_cached_temperature_does_not_restore_observation_counters_or_freshness(rig):
    native = NativeControls(rig[0])
    report(native, 24.5)
    saved = native.snapshot_reported()
    fresh = NativeControls(Core(rig[0].registry))
    fresh.restore_reported(saved)
    field = "shared.current_temperature"
    assert fresh.field_report_view(SERIAL)[field] == {
        "source": "cache",
        "received": 0,
        "accepted": 0,
        "last_received_age": None,
        "last_accepted_age": None,
    }
    assert not fresh.core.available(SERIAL)
    # Metadata-only subscriptions prove connectivity, not sensor freshness.
    fresh.apply(SERIAL, fresh.listing(SERIAL), subscription=True)
    assert fresh.field_report_view(SERIAL)[field]["received"] == 0
    report(fresh, 24.5)
    assert fresh.field_report_view(SERIAL)[field]["source"] == "device"
    assert fresh.field_report_view(SERIAL)[field]["accepted"] == 1


def test_invalid_report_and_credential_rotation_do_not_leave_observation_evidence(rig):
    core = rig[0]
    native = NativeControls(core)
    with pytest.raises(Invalid):
        report(native, True)
    assert native.field_reports == {}
    report(native, 21)
    core.registry.register(SERIAL, "e" * 64, core.caps(SERIAL), rotate=True)
    assert native.field_report_view(SERIAL)["shared.current_temperature"]["source"] == "unknown"
    assert native.field_reports == {}
