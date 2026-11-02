"""Bounded native eco/schedule schemas, independent of HA and file I/O."""

import re

from backend.validation import Invalid, number

MODES = {"HEAT": "heat", "COOL": "cool", "RANGE": "heat_cool"}


def structure_key(value):
    if not isinstance(value, str):
        raise Invalid("native home reference required")
    owner = value.removeprefix("structure.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner):
        raise Invalid("invalid native home reference")
    return "structure." + owner


def schedule(value):
    """Full week, Monday=0; seconds in the thermostat's own local day."""
    if (
        not isinstance(value, dict)
        or set(value) != {"ver", "name", "schedule_mode", "days"}
        or type(value["ver"]) is not int
        or value["ver"] != 2
        or not isinstance(value["schedule_mode"], str)
        or value["schedule_mode"] not in MODES
        or not isinstance(value["name"], str)
        or re.fullmatch(r"[\x20-\x7e]{0,64}", value["name"]) is None
        or not isinstance(value["days"], dict)
        or set(value["days"]) != {str(i) for i in range(7)}
    ):
        raise Invalid("complete version-2 weekly schedule required")
    days = {}
    for day, points in value["days"].items():
        if isinstance(points, dict):
            if set(points) != {str(i) for i in range(len(points))}:
                raise Invalid("contiguous schedule point indices required")
            points = [points[str(i)] for i in range(len(points))]
        if not isinstance(points, list) or len(points) > 24:
            raise Invalid("at most 24 points per day")
        result, previous = {}, -1
        for index, point in enumerate(points):
            if not isinstance(point, dict):
                raise Invalid("schedule point required")
            mode = value["schedule_mode"]
            fields = {"time", "type"} | ({"temp-min", "temp-max"} if mode == "RANGE" else {"temp"})
            if (
                set(point) != fields
                or point["type"] != mode
                or type(point["time"]) is not int
                or not previous < point["time"] < 86400
            ):
                raise Invalid("ordered local-day times and matching schedule mode required")
            previous = point["time"]
            item = {"time": point["time"], "type": mode}
            for key in fields - {"time", "type"}:
                item[key] = number(point[key], 10, 30)
            if mode == "RANGE" and item["temp-min"] >= item["temp-max"]:
                raise Invalid("ordered range targets required")
            result[str(index)] = item
        days[day] = result
    return {"ver": 2, "name": value["name"], "schedule_mode": value["schedule_mode"], "days": days}


def eco_temperatures(value):
    if not isinstance(value, dict) or set(value) != {"low", "high"}:
        raise Invalid("both eco bounds required")
    low, high = number(value["low"], 10, 30), number(value["high"], 10, 30)
    if low >= high:
        raise Invalid("eco low must be below high")
    return {"away_temperature_low": low, "away_temperature_high": high}
