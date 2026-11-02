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


def schedule_record(value):
    """Preserve observed wire shape: Gen2 wrapper or the supported bare week."""
    if not isinstance(value, dict):
        raise Invalid("native schedule record required")
    if set(value) == {"manual_schedule"}:
        return {"manual_schedule": schedule(value["manual_schedule"])}
    return schedule(value)


def schedule_week(value):
    value = schedule_record(value)
    return value.get("manual_schedule", value)


def schedule_shape(value):
    """Finite schema/type evidence only; no names, times or temperatures."""
    from backend.native import json_type

    wrapped = isinstance(value, dict) and set(value) == {"manual_schedule"}
    inner = value.get("manual_schedule") if wrapped else value
    fields = inner if isinstance(inner, dict) else {}
    known = {"ver", "name", "schedule_mode", "days"}
    mode = fields.get("schedule_mode")
    days = fields.get("days")
    point_types, point_fields, point_modes = set(), {}, set()
    unknown_points, max_points = 0, 0
    indices_ok, times_ok, ordered, bounds_ok, point_modes_match = True, True, True, True, True
    if isinstance(days, dict):
        for container in list(days.values())[:7]:
            point_types.add(json_type(container))
            if isinstance(container, dict):
                contiguous = set(container) == {str(i) for i in range(len(container))}
                indices_ok &= contiguous
                points = (
                    [container[str(i)] for i in range(len(container))]
                    if contiguous
                    else list(container.values())
                )
            elif isinstance(container, list):
                points = container
            else:
                indices_ok = False
                continue
            max_points = max(max_points, min(len(points), 25))
            previous = -1
            for point in points[:25]:
                if not isinstance(point, dict):
                    point_types.add(json_type(point))
                    continue
                known_point = {"time", "type", "temp", "temp-min", "temp-max"}
                unknown_points = max(unknown_points, min(len(point.keys() - known_point), 257))
                for key in known_point & point.keys():
                    point_fields.setdefault(key, set()).add(json_type(point[key]))
                point_mode = point.get("type")
                point_modes.add(
                    point_mode
                    if isinstance(point_mode, str) and point_mode in {*MODES, "OFF"}
                    else "other"
                )
                point_modes_match &= point_mode == mode
                when = point.get("time")
                times_ok &= type(when) is int
                if type(when) is int:
                    ordered &= previous < when < 86400
                    previous = when
                for key in {"temp", "temp-min", "temp-max"} & point.keys():
                    target = point[key]
                    bounds_ok &= type(target) in (int, float) and 10 <= target <= 30
    return {
        "format": "wrapped" if wrapped else "bare",
        "value_type": json_type(dict(inner)) if isinstance(inner, dict) else json_type(inner),
        "known_member_types": {
            key: json_type(fields[key]) for key in sorted(known & fields.keys())
        },
        "unknown_member_count": min(len(fields.keys() - known), 257),
        "mode_class": mode if isinstance(mode, str) and mode in {*MODES, "OFF"} else "other",
        "day_count": min(len(days), 8) if isinstance(days, dict) else None,
        "version_is_two": type(fields.get("ver")) is int and fields["ver"] == 2,
        "day_keys_complete": isinstance(days, dict) and set(days) == {str(i) for i in range(7)},
        "name_ascii_bounded": isinstance(fields.get("name"), str)
        and re.fullmatch(r"[\x20-\x7e]{0,64}", fields["name"]) is not None,
        "point_container_types": sorted(point_types),
        "point_known_member_types": {
            key: sorted(types) for key, types in sorted(point_fields.items())
        },
        "point_unknown_member_count_max": unknown_points,
        "point_indices_contiguous": indices_ok,
        "max_points_per_day": max_points,
        "point_mode_classes": sorted(point_modes),
        "point_modes_match": point_modes_match,
        "point_times_integer": times_ok,
        "point_times_ordered_in_day": ordered,
        "point_temperatures_in_supported_bounds": bounds_ok,
    }
