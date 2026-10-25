"""Small fail-closed schemas shared by HTTP, Nest adapter and MQTT."""

import json
import math
import re


class Invalid(ValueError):
    pass


def serial(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{10,32}", value):
        raise Invalid("invalid serial")
    return value


def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise Invalid("number outside allowed range")
    return value


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("duplicate JSON key")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite")),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Invalid("invalid JSON") from exc


def command(body, caps):
    if not isinstance(body, dict) or set(body) != {"operation", "value"}:
        raise Invalid("operation and value required")
    op, value = body["operation"], body["value"]
    if op == "temperature":
        number(value, 10, 30)
    elif op == "mode":
        if not isinstance(value, str) or value not in caps["modes"]:
            raise Invalid("unsupported mode")
    elif op == "fan":
        if not caps["fan"] or value not in ("auto", "on"):
            raise Invalid("unsupported fan")
    else:
        raise Invalid("unsupported operation")
    return dict(body)


def state(body, caps):
    allowed = {"temperature", "target_temperature", "humidity", "mode", "action", "fan", "firmware"}
    if not isinstance(body, dict) or not body or set(body) - allowed:
        raise Invalid("unsupported state field")
    result = dict(body)
    for key, bounds in {
        "temperature": (-40, 80),
        "target_temperature": (5, 35),
        "humidity": (0, 100),
    }.items():
        if key in body:
            number(body[key], *bounds)
    if "mode" in body and (not isinstance(body["mode"], str) or body["mode"] not in caps["modes"]):
        raise Invalid("unsupported mode")
    if "action" in body and body["action"] not in ("off", "idle", "heating", "cooling", "fan"):
        raise Invalid("unsupported action")
    if "fan" in body and (not caps["fan"] or body["fan"] not in ("auto", "on")):
        raise Invalid("unsupported fan")
    if "firmware" in body and (
        not isinstance(body["firmware"], str)
        or not re.fullmatch(r"[A-Za-z0-9._+-]{1,64}", body["firmware"])
    ):
        raise Invalid("invalid firmware version")
    return result


def capabilities(body):
    if not isinstance(body, dict) or set(body) != {"modes", "fan"}:
        raise Invalid("invalid capabilities")
    modes = body["modes"]
    if (
        not isinstance(modes, list)
        or not modes
        or any(not isinstance(m, str) or m not in ("off", "heat", "cool") for m in modes)
        or len(set(modes)) != len(modes)
        or type(body["fan"]) is not bool
    ):
        raise Invalid("invalid capabilities")
    return body
