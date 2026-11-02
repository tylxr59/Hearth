"""Original codec for the statically reviewed Gen2 weather JSON fields."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.validation import Invalid, number

ICONS = {
    "sunny": "sunny",
    "clear-night": "clear",
    "partlycloudy": "partlycloudy",
    "cloudy": "cloudy",
    "fog": "fog",
    "rainy": "rain",
    "pouring": "rain",
    "snowy": "snow",
    "snowy-rainy": "sleet",
    "lightning": "tstorms",
    "lightning-rainy": "tstorms",
    "hail": "sleet",
    "windy": "cloudy",
    "windy-variant": "cloudy",
    "exceptional": "cloudy",
}


def query_location(value):
    # The reviewed native fetcher appends its own postal code and country.
    # Reflect only those bounded fields so a weather response cannot silently
    # replace the unit's country/units with empty location defaults.
    if not isinstance(value, str) or value.count(",") != 1:
        raise Invalid("native postal/country weather query required")
    postal, country = value.split(",")
    if (
        re.fullmatch(r"[A-Za-z0-9 -]{0,15}", postal) is None
        or re.fullmatch(r"[A-Za-z]{2}", country) is None
    ):
        raise Invalid("bounded native postal/country required")
    return {"zip": postal, "country": country.upper()}


def timestamp(value):
    if type(value) is not int or not 0 < value <= 2147483647:
        raise Invalid("weather time outside native signed-32-bit range")
    return value


def payload(current, hourly, daily, timezone, now):
    try:
        zone = ZoneInfo(timezone)
    except (ValueError, ZoneInfoNotFoundError, TypeError) as exc:
        raise Invalid("valid weather timezone required") from exc
    if not isinstance(current, dict) or current.get("condition") not in ICONS:
        raise Invalid("available supported weather condition required")
    current_values = {
        "temp_c": number(current.get("temperature"), -80, 65),
        "humidity": round(number(current.get("humidity"), 0, 100)),
        "icon": ICONS[current["condition"]],
    }
    hours, days = [], []
    for index, point in enumerate(hourly[:48]):
        item = {
            "hour": index + 1,
            "time": timestamp(point["time"]),
            "temp_c": number(point["temperature"], -80, 65),
        }
        if "humidity" in point:
            item["humidity"] = number(point["humidity"], 0, 100)
        hours.append(item)
    for point in daily[:6]:
        low, high = number(point["low"], -80, 65), number(point["high"], -80, 65)
        if low > high:
            raise Invalid("invalid daily weather range")
        item = {"date": timestamp(point["time"]), "temp_low_c": low, "temp_high_c": high}
        if "humidity" in point:
            item["humidity"] = number(point["humidity"], 0, 100)
        days.append(item)
    short_zone = datetime.fromtimestamp(timestamp(now), zone).tzname()
    if not short_zone or len(short_zone) > 15 or len(timezone) > 63:
        raise Invalid("weather timezone exceeds native bounds")
    return {
        "current": current_values,
        "forecast": {"hourly": hours, "daily": days},
        "location": {"timezone": short_zone, "timezone_long": timezone},
    }
