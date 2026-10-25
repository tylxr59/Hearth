"""Experimental, deliberately partial adapter for observed NLE bucket shapes.

No pairing simulation, timestamp reconciliation or power-management claims.
Never auto-enable on a real device. See docs/protocol/nest.md.
"""

from backend.validation import Invalid

DEVICE_FIELDS = {
    "current_temperature": "temperature",
    "current_humidity": "humidity",
    "software_version": "firmware",
}
SHARED_FIELDS = {"target_temperature": "target_temperature", "target_temperature_type": "mode"}


def reports(ident, body):
    if not isinstance(body, dict) or set(body) != {"objects"}:
        raise Invalid("objects required")
    objects = body["objects"]
    if not isinstance(objects, list) or not 1 <= len(objects) <= 2:
        raise Invalid("invalid object count")
    result = {}
    for obj in objects:
        if not isinstance(obj, dict) or set(obj) != {"object_key", "value"}:
            raise Invalid("invalid bucket")
        key, value = obj["object_key"], obj["value"]
        if key == f"device.{ident}":
            mapping = DEVICE_FIELDS
        elif key == f"shared.{ident}":
            mapping = SHARED_FIELDS
        else:
            raise Invalid("bucket ownership or type rejected")
        if not isinstance(value, dict) or not value or set(value) - mapping.keys():
            raise Invalid("unsupported bucket fields")
        for field, data in value.items():
            target = mapping[field]
            if target in result:
                raise Invalid("duplicate field")
            result[target] = data
    return result
