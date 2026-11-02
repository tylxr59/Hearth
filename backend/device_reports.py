"""Bounded native diagnostics, without addresses, identifiers or invented state."""

from backend.validation import Invalid, number

NUMBERS = {
    "battery_level": (0, 6),
    "rssi": (-127, 127),
    "filter_runtime_sec": (0, 9007199254740991),
    "compressor_lockout_timeout": (0, 9007199254740991),
    "outdoor_temperature": (-80, 80),
    "outside_temperature": (-80, 80),
}
BOOLEANS = {"filter_replacement_needed", "sunlight_correction_active"}


def validate(name, value):
    if name in BOOLEANS:
        if type(value) is not bool:
            raise Invalid("reported diagnostic boolean required")
    elif name in NUMBERS:
        number(value, *NUMBERS[name])
    else:
        raise Invalid("unknown diagnostic field")
    return value
