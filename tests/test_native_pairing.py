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


def home_config(paired):
    n, data = paired
    record = data["devices"][SERIAL]
    n.apply(SERIAL, {"objects": [pairing.metadata(record)]}, subscription=True)
    record["home"] = pairing.create_home(1000001)
    n.configure_local_users(data)
    return n, data, record


def test_home_offer_is_user_link_only_and_does_not_invent_baselines(paired):
    n, data, record = home_config(paired)
    assert n.local_user_view(SERIAL)["metadata_acknowledged"]
    body = {"objects": [pairing.metadata(record)]}
    reply = n.apply(SERIAL, body, subscription=True)
    assert reply["objects"] == [pairing.home_announcement(record)]
    assert reply["objects"][0]["value"] == {"user_id": record["user_id"]}
    assert not n.home_key(SERIAL)
    assert not n.control_view(SERIAL)["feature_baselines"]["native_eco_field_observed"]
    assert not n.control_view(SERIAL)["feature_baselines"]["schedule_bucket_observed"]
    assert n.apply(SERIAL, body, subscription=True) == {"objects": []}
    ack = {"objects": [pairing.metadata(record), pairing.home_metadata(record)]}
    n.apply(SERIAL, ack, subscription=True)
    assert n.local_home_view(SERIAL)["metadata_acknowledged"]
    assert not n.local_home_view(SERIAL)["device_reference_observed"]
    assert "structure" not in n.snapshot_reported()["devices"][SERIAL]["records"]
    assert pairing.decode(pairing.encode(data)) == data


def test_home_reference_and_mutable_bucket_versions_remain_device_reported(paired):
    n, _, record = home_config(paired)
    n.updates(SERIAL, {"objects": [pairing.metadata(record)]})
    key = pairing.home_metadata(record)["object_key"]
    n.apply(
        SERIAL, {"objects": [{"object_key": f"device.{SERIAL}", "value": {"structure_id": key}}]}
    )
    n.apply(SERIAL, {"objects": [{"object_key": key, "value": {"manual_eco_all": False}}]})
    assert n.local_home_view(SERIAL)["device_reference_observed"]
    meta = next(row for row in n.listing(SERIAL)["objects"] if row["object_key"] == key)
    assert meta == n._records_for(SERIAL)[key].metadata(key)
    reply = n.updates(SERIAL, {"objects": [meta]})
    assert all("value" not in row for row in reply["objects"])
    assert not n.intents.get(SERIAL)


def test_foreign_reported_home_stops_configured_home_announcements(paired):
    n, _, record = home_config(paired)
    n.apply(
        SERIAL,
        {
            "objects": [
                {
                    "object_key": f"device.{SERIAL}",
                    "value": {"structure_id": "structure.other-home"},
                }
            ]
        },
    )
    assert n.local_home_view(SERIAL)["conflict"]
    assert not n.local_home_view(SERIAL)["offered"]
    reply = n.bootstrap_listing(SERIAL)
    assert pairing.home_metadata(record)["object_key"] not in json.dumps(reply)


def test_home_scope_is_enrollment_bound_and_get_orders_user_before_home(paired):
    n, _, record = home_config(paired)
    reply = n.bootstrap_listing(SERIAL)
    assert reply["objects"][:2] == [pairing.announcement(record), pairing.home_announcement(record)]
    n.core.registry.data["devices"][SERIAL]["hash"] = digest("d" * 64)
    assert not n.local_home_view(SERIAL)["configured"]
    assert not n.local_home_view(SERIAL)["offered"]


@pytest.mark.parametrize("fault", ["id", "extra", "timestamp", "duplicate"])
def test_home_config_refuses_invalid_or_shared_identity(paired, fault):
    _, data, record = home_config(paired)
    if fault == "id":
        record["home"]["id"] = "../escape"
    elif fault == "extra":
        record["home"]["away"] = False
    elif fault == "timestamp":
        record["home"]["timestamp"] = True
    else:
        other = copy.deepcopy(record)
        other["user_id"] = "a" * 32
        data["devices"][OTHER] = other
    with pytest.raises(Invalid):
        pairing.validate(data)


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


def test_home_configuration_does_not_alias_mutable_caller_input(paired):
    n, _, record = home_config(paired)
    key = n.transport_home_key(SERIAL)
    record["home"]["id"] = "b" * 32
    assert n.transport_home_key(SERIAL) == key


def test_malformed_owned_home_metadata_cannot_mutate_device_state(paired):
    n, _, record = home_config(paired)
    before = copy.deepcopy(n.core.states)
    with pytest.raises(Invalid):
        n.apply(
            SERIAL,
            {
                "objects": [
                    {"object_key": f"device.{SERIAL}", "value": {"current_humidity": 77}},
                    {**pairing.home_metadata(record), "object_timestamp": True},
                ]
            },
            subscription=True,
        )
    assert n.core.states == before
