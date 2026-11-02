import pytest

from backend.native_controls import NativeControls
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub


@pytest.fixture
def home(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"device.{SERIAL}", "value": {"structure_id": "structure.ECOLAB"}},
                {
                    "object_key": "structure.ECOLAB",
                    "value": {"manual_eco_all": False, "manual_eco_timestamp": 900},
                },
            ]
        },
    )
    return n


def report(n, mode, **metadata):
    n.apply(
        SERIAL,
        {
            "objects": [
                {"object_key": f"device.{SERIAL}", "value": {"eco": {"mode": mode}}, **metadata}
            ]
        },
    )


def write(n, value):
    n.enqueue(SERIAL, {"operation": "eco", "value": value})
    response = n.updates(SERIAL, sub(n))
    n.note_stream_write(SERIAL, response)


def test_fresh_mode_confirms_manual_on_without_scalar_timestamp_echo(home):
    n = home
    write(n, True)
    report(n, "manual-eco")
    receipt = n.control_view(SERIAL)["delivery_receipts"]["eco"]
    assert receipt["outcome"] == "confirmed" and receipt["confirmation_source"] == "device_eco_mode"
    assert receipt["matching_reported_field_count"] == receipt["required_field_count"] == 1
    assert n.reported[SERIAL]["structure"]["values"]["manual_eco_all"] is False
    assert n.eco_mode(SERIAL) == "manual-eco" and n.updates(SERIAL, sub(n)) == {"objects": []}


@pytest.mark.parametrize("mode", ["schedule", "auto-eco"])
def test_manual_off_preserves_automatic_eco_semantics(home, mode):
    write(home, False)
    report(home, mode)
    assert home.command_status(SERIAL)["eco"] == "confirmed"
    assert home.eco_mode(SERIAL) == mode


def test_cached_mode_and_metadata_do_not_confirm(home):
    report(home, "manual-eco")
    home.enqueue(SERIAL, {"operation": "eco", "value": True})
    home.apply(SERIAL, sub(home), subscription=True)
    assert home.command_status(SERIAL)["eco"] == "pending"


def test_stale_conditional_mode_cannot_confirm(home):
    write(home, True)
    report(home, "manual-eco", if_object_revision=0)
    assert home.command_status(SERIAL)["eco"] == "pending"


def test_unknown_mode_cannot_confirm(home):
    write(home, True)
    report(home, "unsupported")
    assert home.command_status(SERIAL)["eco"] == "pending"


def test_local_mode_change_wins_after_written_request(home):
    write(home, True)
    report(home, "schedule")
    assert home.command_status(SERIAL)["eco"] == "superseded_by_device"
    assert home.updates(SERIAL, sub(home)) == {"objects": []}


def test_late_actual_mode_updates_reading_without_confirming_expired_request(home, rig):
    write(home, True)
    rig[3][0] += 31
    report(home, "manual-eco")
    assert home.command_status(SERIAL)["eco"] == "expired" and home.eco_mode(SERIAL) == "manual-eco"
