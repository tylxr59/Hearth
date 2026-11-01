"""Strict reported-state cache codec. No file I/O, commands or fresh-state claim.

Only fixed native reported fields may cross this boundary. Pending intents,
unknown native values, credentials and runtime fingerprints are excluded.
"""

import json
import re

from backend.native import integer
from backend.validation import Invalid, loads, number, serial

FORMAT = "hearth-reported-native-state-v1"
LIMIT = 512 * 1024
FLAGS = {
    "can_heat",
    "can_cool",
    "has_fan",
    "has_emer_heat",
    "hvac_heater_state",
    "hvac_heat_x2_state",
    "hvac_heat_x3_state",
    "hvac_aux_heater_state",
    "hvac_alt_heat_state",
    "hvac_ac_state",
    "hvac_cool_x2_state",
    "hvac_cool_x3_state",
    "hvac_fan_state",
}
FIELDS = {
    "device": {
        "current_temperature",
        "current_humidity",
        "software_version",
        "fan_timer_timeout",
        "can_heat",
        "can_cool",
        "has_fan",
        "has_emer_heat",
    },
    "shared": {
        "current_temperature",
        "target_temperature",
        "target_temperature_low",
        "target_temperature_high",
        "target_temperature_type",
    }
    | FLAGS,
}


def reported_value(name, value):
    if name in FLAGS:
        if type(value) is not bool:
            raise Invalid("reported flag must be boolean")
    elif name == "fan_timer_timeout":
        integer(value)
    elif name == "target_temperature_type":
        if not isinstance(value, str) or value not in ("off", "heat", "cool", "range", "emergency"):
            raise Invalid("unsupported reported mode")
    elif name == "software_version":
        if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", value) is None:
            raise Invalid("invalid reported firmware")
    else:
        low, high = {
            "current_temperature": (-40, 80),
            "current_humidity": (0, 100),
            "target_temperature": (5, 35),
            "target_temperature_low": (5, 35),
            "target_temperature_high": (5, 35),
        }[name]
        number(value, low, high)
    return value


def validate(data):
    if (
        not isinstance(data, dict)
        or set(data) != {"format", "saved_at", "devices"}
        or data["format"] != FORMAT
    ):
        raise Invalid("reported cache envelope required")
    integer(data["saved_at"])
    devices = data["devices"]
    if not isinstance(devices, dict) or len(devices) > 64:
        raise Invalid("reported cache device limit")
    result = {}
    for ident, entry in devices.items():
        serial(ident)
        if (
            not isinstance(entry, dict)
            or set(entry) != {"generation", "records"}
            or not isinstance(entry["generation"], str)
            or re.fullmatch("[0-9a-f]{64}", entry["generation"]) is None
        ):
            raise Invalid("reported cache generation required")
        records = entry["records"]
        if not isinstance(records, dict) or not set(records) <= FIELDS.keys():
            raise Invalid("reported cache bucket scope")
        clean = {}
        for kind, record in records.items():
            if not isinstance(record, dict) or set(record) != {"revision", "timestamp", "values"}:
                raise Invalid("reported cache record shape")
            integer(record["revision"])
            integer(record["timestamp"])
            values = record["values"]
            if not isinstance(values, dict) or not set(values) <= FIELDS[kind]:
                raise Invalid("unknown reported cache field")
            clean[kind] = {
                "revision": record["revision"],
                "timestamp": record["timestamp"],
                "values": {name: reported_value(name, value) for name, value in values.items()},
            }
        result[ident] = {"generation": entry["generation"], "records": clean}
    return {"format": FORMAT, "saved_at": data["saved_at"], "devices": result}


def encode(data):
    raw = json.dumps(
        validate(data), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(raw) > LIMIT:
        raise Invalid("reported cache size limit")
    return raw


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > LIMIT:
        raise Invalid("bounded reported cache bytes required")
    return validate(loads(raw))
