"""Explicit local user announcement; configuration, never reported device state.

The first step supplies user.name. A separate confirmed action adds a private
home identity and user link. Neither creates schedule, equipment or eco baselines.
"""

import json
import re
import uuid

from backend.native import integer
from backend.registry import token_valid
from backend.validation import Invalid, loads, serial

FORMAT = "hearth-local-user-v1"
NAME = "local-pairing.json"


def validate(data):
    if not isinstance(data, dict) or set(data) != {"format", "devices"} or data["format"] != FORMAT:
        raise Invalid("local pairing configuration required")
    if not isinstance(data["devices"], dict) or len(data["devices"]) > 64:
        raise Invalid("bounded local pairing devices required")
    result, users, homes = {}, set(), set()
    for ident, record in data["devices"].items():
        serial(ident)
        if not isinstance(record, dict) or set(record) - {"home"} != {
            "generation",
            "user_id",
            "revision",
            "timestamp",
        }:
            raise Invalid("local pairing record required")
        user = record["user_id"]
        if (
            not token_valid(record["generation"])
            or not isinstance(user, str)
            or not re.fullmatch(r"[0-9a-f]{32}", user)
            or user in users
        ):
            raise Invalid("unique enrollment-bound local user required")
        if integer(record["revision"]) != 1 or integer(record["timestamp"]) == 0:
            raise Invalid("local user metadata required")
        if "home" in record:
            home = record["home"]
            if (
                not isinstance(home, dict)
                or set(home) != {"id", "timestamp"}
                or not isinstance(home["id"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", home["id"])
                or integer(home["timestamp"]) == 0
                or home["id"] in homes
            ):
                raise Invalid("explicit unique local home identity required")
            homes.add(home["id"])
        users.add(user)
        result[ident] = dict(record)
        if "home" in record:
            result[ident]["home"] = dict(record["home"])
    return {"format": FORMAT, "devices": result}


def encode(data):
    return json.dumps(validate(data), sort_keys=True, separators=(",", ":")).encode()


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise Invalid("bounded local pairing bytes required")
    return validate(loads(raw))


def create(generation, timestamp):
    return {
        "generation": generation,
        "user_id": uuid.uuid4().hex,
        "revision": 1,
        "timestamp": integer(timestamp),
    }


def metadata(record):
    return {
        "object_revision": record["revision"],
        "object_timestamp": record["timestamp"],
        "object_key": "user." + record["user_id"],
    }


def announcement(record):
    return metadata(record) | {"value": {"name": "Hearth"}}


def home_metadata(record):
    return {
        "object_revision": 1,
        "object_timestamp": record["home"]["timestamp"],
        "object_key": "structure." + record["home"]["id"],
    }


def home_announcement(record):
    # Identity and the reviewed user link only. No away/eco/safety defaults.
    return home_metadata(record) | {"value": {"user_id": record["user_id"]}}


def create_home(timestamp):
    return {"id": uuid.uuid4().hex, "timestamp": integer(timestamp)}
