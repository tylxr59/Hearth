import json

import pytest

from backend import native_features as features
from backend import schedule_backup
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline, sub


def week(mode="HEAT"):
    point = {"time": 21600, "type": mode}
    point.update({"temp-min": 18, "temp-max": 25} if mode == "RANGE" else {"temp": 20})
    return {
        "ver": 2,
        "name": "Week",
        "schedule_mode": mode,
        "days": {str(i): [dict(point)] for i in range(7)},
    }


@pytest.fixture
def featured(rig):
    rig[0].registry.data["devices"][SERIAL]["capabilities"]["modes"].append("heat_cool")
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {
                        "structure_id": "structure.LABHOME",
                        "away_temperature_low": 16,
                        "away_temperature_high": 27,
                    },
                },
                {
                    "object_key": "structure.LABHOME",
                    "value": {"manual_eco_all": False, "manual_eco_timestamp": 900},
                },
                {"object_key": f"shared.{SERIAL}", "value": {"schedule_mode": "HEAT"}},
                {"object_key": f"schedule.{SERIAL}", "value": week()},
            ]
        },
    )
    return n


@pytest.mark.parametrize("mode", ["HEAT", "COOL", "RANGE"])
def test_complete_week_canonicalization_and_detached_copy(mode):
    original = week(mode)
    normalized = features.schedule(original)
    assert len(normalized["days"]) == 7 and "0" in normalized["days"]["0"]
    assert features.schedule(normalized) == normalized
    normalized["days"]["0"]["0"]["time"] = 0
    assert original["days"]["0"][0]["time"] == 21600


@pytest.mark.parametrize(
    "fault",
    [
        "missing_day",
        "extra_day",
        "bool_version",
        "unknown_field",
        "missing_temp",
        "bool_time",
        "duplicate_time",
        "unordered",
        "bad_mode",
        "bool_temp",
        "nan",
        "gap_index",
        "too_many",
        "range_order",
    ],
)
def test_bad_schedule_fails_without_mutation(fault):
    s = week("RANGE" if fault == "range_order" else "HEAT")
    p = s["days"]["0"][0]
    if fault == "missing_day":
        del s["days"]["6"]
    elif fault == "extra_day":
        s["days"]["7"] = []
    elif fault == "bool_version":
        s["ver"] = True
    elif fault == "unknown_field":
        p["credential"] = "forbidden"
    elif fault == "missing_temp":
        del p["temp"]
    elif fault == "bool_time":
        p["time"] = True
    elif fault == "duplicate_time":
        s["days"]["0"].append(dict(p))
    elif fault == "unordered":
        s["days"]["0"].append(dict(p, time=1))
    elif fault == "bad_mode":
        p["type"] = "COOL"
    elif fault == "bool_temp":
        p["temp"] = False
    elif fault == "nan":
        p["temp"] = float("nan")
    elif fault == "gap_index":
        s["days"]["0"] = {"1": p}
    elif fault == "too_many":
        s["days"]["0"] = [dict(p, time=i) for i in range(25)]
    elif fault == "range_order":
        p["temp-min"] = 29
    with pytest.raises(Invalid):
        features.schedule(s)


def test_eco_only_bound_reference_and_subscription_values(featured):
    before = sub(featured)
    featured.enqueue(SERIAL, {"operation": "eco", "value": True})
    result = featured.updates(SERIAL, before)
    assert result["objects"][0]["object_key"] == "structure.LABHOME"
    assert result["objects"][0]["value"] == {"manual_eco_all": True, "manual_eco_timestamp": 1000}
    reply = featured.apply(
        SERIAL,
        {"objects": [{"object_key": "structure.LABHOME", "value": result["objects"][0]["value"]}]},
    )
    assert all("value" not in row for row in reply["objects"])
    assert featured.command_status(SERIAL)["eco"] == "confirmed"
    assert featured.apply(
        SERIAL, {"objects": [{"object_key": "structure.OTHER", "value": {"manual_eco_all": False}}]}
    ) == {"objects": []}


def test_unreferenced_structure_never_enables_eco(rig):
    n = NativeControls(rig[0])
    baseline(n)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": "structure.LABHOME",
                    "value": {"manual_eco_all": False, "manual_eco_timestamp": 900},
                }
            ]
        },
    )
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, {"operation": "eco", "value": True})
    assert not n.home_key(SERIAL) and "structure.LABHOME" not in n._records_for(SERIAL)


def test_reference_change_discards_old_home_and_pending_eco(featured):
    featured.enqueue(SERIAL, {"operation": "eco", "value": True})
    featured.apply(
        SERIAL,
        {"objects": [{"object_key": f"device.{SERIAL}", "value": {"structure_id": "OTHER"}}]},
    )
    assert featured.home_key(SERIAL) == "structure.OTHER"
    assert "structure.LABHOME" not in featured._records_for(SERIAL)
    assert "structure" not in featured.reported[SERIAL]
    assert not featured.intents[SERIAL]
    with pytest.raises(Invalid):
        featured.enqueue(SERIAL, {"operation": "eco", "value": False})


def test_null_reference_disables_eco_without_losing_telemetry(featured):
    featured.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {"structure_id": None, "current_humidity": 55},
                }
            ]
        },
    )
    assert featured.home_key(SERIAL) is None
    assert featured.core.states[SERIAL]["humidity"] == 55
    assert "structure.LABHOME" not in featured._records_for(SERIAL)


def test_week_requires_backup_and_cas_then_replaces_all_days(featured, tmp_path):
    tmp_path.chmod(0o700)
    revision = featured._records_for(SERIAL)[f"schedule.{SERIAL}"].revision
    new = week()
    new["days"]["0"] = []
    body = {"operation": "schedule", "value": new, "expected_revision": revision}
    with pytest.raises(Invalid):
        featured.enqueue(SERIAL, body)
    previous = featured.reported[SERIAL]["schedule"]["values"]
    name = schedule_backup.archive(tmp_path, SERIAL, "a" * 64, revision, previous)
    assert (tmp_path / name).stat().st_mode & 0o777 == 0o600
    assert json.loads((tmp_path / name).read_bytes())["schedule"] == features.schedule(week())
    request = sub(featured)
    featured.enqueue(SERIAL, body, schedule_backed_up=True)
    row = featured.updates(SERIAL, request)["objects"][0]
    assert row["value"]["days"]["0"] == {} and set(row["value"]) == {
        "ver",
        "name",
        "schedule_mode",
        "days",
    }
    with pytest.raises(Invalid):
        featured.enqueue(SERIAL, body, schedule_backed_up=True)
    featured.apply(SERIAL, {"objects": [{"object_key": row["object_key"], "value": row["value"]}]})
    assert featured.command_status(SERIAL)["schedule"] == "confirmed"


def test_feature_cache_restart_has_no_intent(featured, rig):
    snapshot = featured.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    n = NativeControls(rig[0], clock=lambda: 1000)
    n.restore_reported(snapshot)
    assert n.home_key(SERIAL) == "structure.LABHOME"
    assert n.reported[SERIAL]["schedule"]["values"] == features.schedule(week())
    assert not n.intents and not rig[0].available(SERIAL)


def test_native_schedule_edit_racing_backup_refuses_old_revision(featured):
    record = featured._records_for(SERIAL)[f"schedule.{SERIAL}"]
    body = {"operation": "schedule", "value": week(), "expected_revision": record.revision}
    featured.advanced_plan(SERIAL, body, True)
    edited = week()
    edited["days"]["0"][0]["temp"] = 23
    featured.apply(SERIAL, {"objects": [{"object_key": f"schedule.{SERIAL}", "value": edited}]})
    with pytest.raises(Invalid):
        featured.enqueue(SERIAL, body, schedule_backed_up=True)
    assert not featured.intents
    assert featured.reported[SERIAL]["schedule"]["values"]["days"]["0"]["0"]["temp"] == 23


def test_archive_failure_does_not_return_success(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)

    def fail(_):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(schedule_backup.os, "fsync", fail)
    with pytest.raises(OSError):
        schedule_backup.archive(tmp_path, SERIAL, "a" * 64, 1, week())
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in tmp_path.iterdir())


def test_cache_only_schedule_is_not_a_replacement_baseline(featured, rig):
    snapshot = featured.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    n = NativeControls(rig[0], clock=lambda: 1000)
    n.restore_reported(snapshot)
    n.core.touch(SERIAL)
    body = {
        "operation": "schedule",
        "value": week(),
        "expected_revision": n._records_for(SERIAL)[f"schedule.{SERIAL}"].revision,
    }
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, body, schedule_backed_up=True)
    assert not n.intents


def test_partial_schedule_delta_does_not_freshen_cached_days(featured, rig):
    snapshot = featured.snapshot_reported()
    rig[0].states.clear()
    rig[0].seen.clear()
    n = NativeControls(rig[0], clock=lambda: 1000)
    n.restore_reported(snapshot)
    n.core.touch(SERIAL)
    n.apply(
        SERIAL,
        {"objects": [{"object_key": f"schedule.{SERIAL}", "value": {"schedule_mode": "HEAT"}}]},
    )
    body = {
        "operation": "schedule",
        "value": week(),
        "expected_revision": n._records_for(SERIAL)[f"schedule.{SERIAL}"].revision,
    }
    with pytest.raises(Invalid):
        n.enqueue(SERIAL, body, schedule_backed_up=True)
    assert ("schedule", "days") in n.restored_fields[SERIAL]
    n.apply(SERIAL, {"objects": [{"object_key": f"schedule.{SERIAL}", "value": week()}]})
    body["expected_revision"] = n._records_for(SERIAL)[f"schedule.{SERIAL}"].revision
    assert n.advanced_plan(SERIAL, body, True)[0] == "schedule"
