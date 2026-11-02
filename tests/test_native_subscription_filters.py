import copy
import json
import secrets

import pytest

from backend.native import BucketShapeError, NativeTelemetry
from backend.native_controls import NativeControls
from backend.validation import Invalid
from tests.conftest import OTHER, SERIAL
from tests.test_native_controls import baseline


@pytest.mark.parametrize("named", [True, False])
def test_empty_native_filters_accept_metadata_only_and_never_create_values(rig, named):
    native = NativeControls(rig[0])
    baseline(native)
    before = copy.deepcopy(native.core.states)
    rows = [{**row, "filters": []} for row in native.listing(SERIAL)["objects"]]
    incoming = (
        {"chunked": False, **{row["object_key"].split(".")[0]: row for row in rows}}
        if named
        else {"objects": rows}
    )
    reply = native.apply(SERIAL, incoming, subscription=True)
    assert all("value" not in row for row in reply["objects"])
    assert native.core.states == before
    assert native.diagnostics()["empty_subscription_filters_accepted"] is True


@pytest.mark.parametrize(
    "filters", [None, False, "*", {}, ["*"], ["secret"], [{"path": "credential"}]]
)
def test_nonempty_or_invalid_filters_refuse_without_mutation_or_value_retention(rig, filters):
    native = NativeTelemetry(rig[0])
    before = copy.deepcopy(native.core.states)
    incoming = {"objects": [{"object_key": f"device.{SERIAL}", "filters": filters}]}
    with pytest.raises(BucketShapeError) as error:
        native.apply(SERIAL, incoming, subscription=True)
    native.reject(error.value)
    assert native.core.states == before and not native._records
    diagnostic = native.diagnostics()["last_bucket_shape"]
    assert diagnostic["detail"] == "nonempty_or_invalid_filters"
    assert "secret" not in json.dumps(diagnostic) and "credential" not in json.dumps(diagnostic)


def test_filters_are_not_a_put_value_or_an_ownership_escape(rig):
    native = NativeTelemetry(rig[0])
    with pytest.raises(Invalid):
        native.apply(
            SERIAL,
            {
                "objects": [
                    {
                        "object_key": f"device.{SERIAL}",
                        "filters": [],
                        "value": {"current_temperature": 20},
                    }
                ]
            },
        )
    with pytest.raises(Invalid):
        native.apply(
            SERIAL,
            {"objects": [{"object_key": f"device.{OTHER}", "filters": []}]},
            subscription=True,
        )
    assert native.apply(
        SERIAL, {"objects": [{"object_key": "structure.FOREIGN", "filters": []}]}, subscription=True
    ) == {"objects": []}


def test_rejected_shape_diagnostics_never_retain_unknown_names_or_values(rig):
    name, value = secrets.token_hex(32), secrets.token_hex(32)
    native = NativeTelemetry(rig[0])
    obj = {"object_key": f"device.{SERIAL}", "object_revision": 0, "filters": [], name: value}
    with pytest.raises(BucketShapeError) as error:
        native.apply(SERIAL, {"objects": [obj]}, subscription=True)
    native.reject(error.value)
    diagnostic = native.diagnostics()
    shape = diagnostic["last_bucket_shape"]
    assert shape["unknown_member_count"] == 1 and shape["filter_count"] == 0
    assert shape["known_member_types"] == {
        "filters": "array",
        "object_key": "string",
        "object_revision": "integer",
    }
    assert all(marker not in json.dumps(diagnostic) for marker in (name, value, SERIAL))
    diagnostic["last_bucket_shape"]["known_member_types"].clear()
    assert native.diagnostics()["last_bucket_shape"]["known_member_types"]
