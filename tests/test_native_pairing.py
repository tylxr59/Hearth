import copy
import json

import pytest

from backend import native_pairing as pairing
from backend import reported_store
from backend.native_controls import NativeControls
from backend.registry import digest
from backend.validation import Invalid
from tests.conftest import OTHER, SERIAL
from tests.test_native_controls import baseline


def config(native, ident=SERIAL):
    return {
        "format": pairing.FORMAT,
        "devices": {
            ident: pairing.create(native.core.registry.data["devices"][ident]["hash"], 1000000)
        },
    }


@pytest.fixture
def paired(rig):
    n = NativeControls(rig[0], clock=lambda: 1000)
    baseline(n)
    data = config(n)
    n.configure_local_users(data)
    return n, data


def test_pairing_is_explicit_separate_configuration_and_offers_only_name(paired):
    n, data = paired
    before = copy.deepcopy(n.core.states)
    body = {"objects": [{"object_key": f"device.{SERIAL}", "object_revision": 0}]}
    result = n.apply(SERIAL, body, subscription=True)
    row = result["objects"][0]
    assert row == pairing.announcement(data["devices"][SERIAL])
    assert list(row) == ["object_revision", "object_timestamp", "object_key", "value"]
    assert n.core.states == before
    snapshot = n.snapshot_reported()
    assert "user" not in snapshot["devices"][SERIAL]["records"]
    assert data["devices"][SERIAL]["user_id"] not in json.dumps(snapshot)
    assert not n.home_key(SERIAL) and "schedule" not in n.reported[SERIAL]
    # Missing acknowledgement cannot cause an endless configuration push loop.
    assert all(not r.get("value") for r in n.apply(SERIAL, body, subscription=True)["objects"])


def test_only_own_enrollment_can_acknowledge_and_no_put_values_are_added(paired):
    n, data = paired
    record = data["devices"][SERIAL]
    n.apply(SERIAL, {"objects": [pairing.metadata(record)]}, subscription=True)
    assert n.local_user_view(SERIAL) == {
        "configured": True,
        "offered": True,
        "metadata_acknowledged": True,
    }
    reply = n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": pairing.metadata(record)["object_key"],
                    "value": {"name": "ignored", "unknown": "never-retain"},
                }
            ]
        },
    )
    assert reply == {"objects": []}
    assert "never-retain" not in repr(n.__dict__)
    assert record["user_id"] not in json.dumps(n.control_view(SERIAL))


def test_invalid_owned_user_metadata_cannot_partially_mutate_device(paired):
    n, data = paired
    before = copy.deepcopy(n.core.states)
    record = data["devices"][SERIAL]
    with pytest.raises(Invalid):
        n.apply(
            SERIAL,
            {
                "objects": [
                    {"object_key": f"device.{SERIAL}", "value": {"current_humidity": 52}},
                    {**pairing.metadata(record), "value": {"name": "Hearth"}},
                ]
            },
            subscription=True,
        )
    assert n.core.states == before


def test_local_user_keys_are_device_scoped_and_generation_bound(paired, rig):
    n, data = paired
    rig[0].registry.register(OTHER, "b" * 64, {"modes": ["off"], "fan": False})
    n.configure_local_users(config(n, OTHER))
    own = data["devices"][SERIAL]["user_id"]
    other = n._local_users[OTHER]["user_id"]
    assert own != other
    result = n.apply(OTHER, {"objects": [{"object_key": f"device.{OTHER}"}]}, subscription=True)
    assert own not in json.dumps(result) and other in json.dumps(result)
    rig[0].registry.data["devices"][SERIAL]["hash"] = digest("c" * 64)
    assert n.local_user_view(SERIAL)["configured"] is False
    n.configure_local_users(data)
    assert n.local_user_view(SERIAL)["configured"] is False


def test_local_pairing_store_is_private_and_not_the_reported_cache(tmp_path, paired):
    tmp_path.chmod(0o700)
    _, data = paired
    reported_store.save(tmp_path, data, pairing.NAME, pairing.encode, pairing.decode)
    assert reported_store.load(tmp_path, pairing.NAME, pairing.decode) == data
    assert (tmp_path / pairing.NAME).stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / reported_store.NAME).exists()
    (tmp_path / pairing.NAME).chmod(0o644)
    with pytest.raises(Invalid):
        reported_store.save(tmp_path, data, pairing.NAME, pairing.encode, pairing.decode)
    with pytest.raises(Invalid):
        reported_store.load(tmp_path, "../escape.json", pairing.decode)


@pytest.mark.parametrize(
    "fault",
    ["extra", "duplicate_user", "bad_generation", "bad_id", "bool_revision", "zero_timestamp"],
)
def test_pairing_configuration_refuses_ambiguous_or_unsafe_records(paired, fault):
    _, original = paired
    data = copy.deepcopy(original)
    record = data["devices"][SERIAL]
    if fault == "extra":
        record["credential"] = "forbidden"
    elif fault == "duplicate_user":
        data["devices"][OTHER] = dict(record)
    elif fault == "bad_generation":
        record["generation"] = "not-a-generation"
    elif fault == "bad_id":
        record["user_id"] = "../../bad"
    elif fault == "bool_revision":
        record["revision"] = True
    elif fault == "zero_timestamp":
        record["timestamp"] = 0
    with pytest.raises(Invalid):
        pairing.encode(data)
