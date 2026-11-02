import copy

import pytest

from backend.native import RevisionError
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import SERIAL
from tests.test_native_controls import baseline
from tests.test_native_features import week


def test_native_overwrite_replaces_schedule_and_preserves_other_telemetry(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    key = f"schedule.{SERIAL}"
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": week()}]})
    result = n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": key,
                    "base_object_revision": -1,
                    "op": "OVERWRITE",
                    "value": {"manual_schedule": week()},
                },
                {"object_key": f"device.{SERIAL}", "value": {"current_humidity": 51}},
            ]
        },
    )
    assert len(result["objects"]) == 2
    assert n.core.states[SERIAL]["humidity"] == 51
    assert set(n._records_for(SERIAL)[key].fingerprints) == {"manual_schedule"}
    values = n.snapshot_reported()["devices"][SERIAL]["records"]["schedule"]["values"]
    assert set(values) == {"manual_schedule"}
    assert "op" not in n._records_for(SERIAL)[key].fingerprints
    assert not n.intents.get(SERIAL)


def test_unknown_week_is_received_but_cannot_become_a_valid_control_baseline(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    key = f"schedule.{SERIAL}"
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": week()}]})
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": key,
                    "op": "OVERWRITE",
                    "value": {"unknown_native_field": "not-retained"},
                }
            ]
        },
    )
    assert set(n._records_for(SERIAL)[key].fingerprints) == {"unknown_native_field"}
    assert "schedule" not in n.reported[SERIAL]
    shape = n.control_view(SERIAL)["feature_baselines"]["schedule_shape"]
    assert shape["unknown_member_count"] == 1 and not shape["known_member_types"]
    assert "not-retained" not in repr(shape) and SERIAL not in repr(shape)
    assert "not-retained" not in repr(n.__dict__)
    with pytest.raises(Invalid):
        n.advanced_plan(
            SERIAL,
            {
                "operation": "schedule",
                "value": week(),
                "expected_revision": n._records_for(SERIAL)[key].revision,
            },
            True,
        )


@pytest.mark.parametrize(
    "kind,op,subscription",
    [
        ("device", "OVERWRITE", False),
        ("shared", "OVERWRITE", False),
        ("schedule", "DELETE", False),
        ("schedule", True, False),
        ("schedule", "OVERWRITE", True),
    ],
)
def test_unsupported_operations_fail_before_any_mutation(rig, kind, op, subscription):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    before = copy.deepcopy(n.core.states)
    with pytest.raises(Invalid):
        n.apply(
            SERIAL,
            {
                "objects": [
                    {"object_key": f"device.{SERIAL}", "value": {"current_humidity": 51}},
                    {"object_key": f"{kind}.{SERIAL}", "op": op, "value": week()},
                ]
            },
            subscription=subscription,
        )
    assert n.core.states == before


@pytest.mark.parametrize("field", ["object_revision", "object_timestamp", "if_object_revision"])
def test_negative_control_metadata_remains_rejected_with_value_free_evidence(rig, field):
    n = NativeControls(rig[0])
    with pytest.raises(RevisionError) as caught:
        n.apply(
            SERIAL,
            {
                "objects": [
                    {"object_key": f"device.{SERIAL}", field: -1, "value": {"current_humidity": 51}}
                ]
            },
        )
    n.reject(caught.value)
    evidence = n.diagnostics()["last_revision_error"]
    assert evidence["field"] == field and evidence["is_minus_one"]
    assert evidence["known_bucket_kind"] == "device" and SERIAL not in repr(evidence)
    assert "value" not in evidence


@pytest.mark.parametrize("base", [-1, -2, -(1 << 31), -1000000000])
def test_signed_base_is_put_only_and_does_not_disable_cas(rig, base):
    n = NativeControls(rig[0])
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "base_object_revision": base,
                    "if_object_revision": 99,
                    "value": {"current_humidity": 51},
                }
            ]
        },
    )
    assert not n.core.states
    with pytest.raises(RevisionError):
        n.apply(
            SERIAL,
            {"objects": [{"object_key": f"device.{SERIAL}", "base_object_revision": base}]},
            subscription=True,
        )


@pytest.mark.parametrize("base", [-(1 << 31) - 1, -1.0, True])
def test_signed_base_bounds_and_type_are_enforced(rig, base):
    n = NativeControls(rig[0])
    with pytest.raises(RevisionError):
        n.apply(
            SERIAL,
            {
                "objects": [
                    {
                        "object_key": f"device.{SERIAL}",
                        "base_object_revision": base,
                        "value": {"current_humidity": 51},
                    }
                ]
            },
        )
    assert not n.core.states


@pytest.mark.parametrize("revision", [-1, -123456789, -(1 << 31)])
def test_signed_subscription_version_only_requests_current_metadata(rig, revision):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    before = copy.deepcopy(n.core.states)
    key = f"device.{SERIAL}"
    previous = n._records_for(SERIAL)[key].metadata(key)
    result = n.apply(
        SERIAL,
        {"objects": [{"object_key": key, "object_revision": revision, "object_timestamp": 0}]},
        subscription=True,
    )
    assert result == {"objects": [previous]}
    assert n._records_for(SERIAL)[key].revision >= 0
    assert n.core.states == before and not n.intents.get(SERIAL)
    with pytest.raises(RevisionError):
        n.apply(
            SERIAL,
            {
                "objects": [
                    {
                        "object_key": key,
                        "object_revision": revision,
                        "value": {"current_humidity": 77},
                    }
                ]
            },
            subscription=True,
        )


def test_subscription_signed_version_is_bounded_and_never_relaxes_timestamps(rig):
    n = NativeControls(rig[0])
    for fields in (
        {"object_revision": -(1 << 31) - 1},
        {"object_revision": -1, "object_timestamp": -1},
        {"object_revision": -1, "if_object_revision": -1},
    ):
        with pytest.raises(RevisionError):
            n.apply(
                SERIAL,
                {"objects": [{"object_key": f"device.{SERIAL}", **fields}]},
                subscription=True,
            )
    assert not n.core.states
