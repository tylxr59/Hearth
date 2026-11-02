"""Use HA's configured weather entity; no direct Internet client or geocoding."""

import asyncio
import time

from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from ._backend import native_weather
from ._backend.validation import Invalid, number


class HAWeatherSource:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.cache = {}
        self.lock = asyncio.Lock()
        self.requests = self.failures = 0

    def entity_id(self):
        configured = self.entry.options.get("weather_entity")
        if configured == "disabled":
            return None
        if isinstance(configured, str):
            return configured if configured.startswith("weather.") else None
        candidates = self.hass.states.async_entity_ids("weather")
        return candidates[0] if len(candidates) == 1 else None

    def enabled(self):
        return self.entity_id() is not None

    async def forecasts(self, source, kind, unit):
        key = source, kind, unit
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
        try:
            async with asyncio.timeout(10):
                result = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": source, "type": kind},
                    blocking=True,
                    return_response=True,
                )
            rows = result[source]["forecast"]
            if not isinstance(rows, list) or len(rows) > 512:
                raise Invalid("bounded HA weather forecast required")
            self.cache[key] = time.monotonic(), rows
            return rows
        except (HomeAssistantError, TimeoutError, Invalid, KeyError, TypeError, ValueError):
            # Current weather remains usable; never invent forecasts or return
            # indefinitely stale cached forecasts when the source fails.
            self.failures = min(self.failures + 1, 2147483647)
            return []

    async def payload(self):
        async with self.lock:
            self.requests = min(self.requests + 1, 2147483647)
            source = self.entity_id()
            state = self.hass.states.get(source) if source else None
            if state is None or state.state in ("unavailable", "unknown"):
                raise Invalid("HA weather source unavailable")
            now = dt_util.utcnow()
            if (now - state.last_reported).total_seconds() > 7200:
                raise Invalid("HA weather source is stale")
            unit = state.attributes.get("temperature_unit")
            if unit not in ("°C", "°F"):
                raise Invalid("supported HA weather temperature unit required")

            def celsius(value):
                number(value, -112 if unit == "°F" else -80, 149 if unit == "°F" else 65)
                return TemperatureConverter.convert(value, unit, "°C")

            current = {
                "condition": state.state,
                "temperature": celsius(state.attributes.get("temperature")),
                "humidity": number(state.attributes.get("humidity"), 0, 100),
            }
            forecasts = {"hourly": [], "daily": []}
            supported = state.attributes.get("supported_features", 0)
            for kind, flag in (
                ("hourly", WeatherEntityFeature.FORECAST_HOURLY),
                ("daily", WeatherEntityFeature.FORECAST_DAILY),
            ):
                if (
                    not isinstance(supported, int)
                    or isinstance(supported, bool)
                    or not supported & flag
                ):
                    continue
                for point in await self.forecasts(source, kind, unit):
                    try:
                        when = dt_util.parse_datetime(point["datetime"])
                        if (
                            when is None
                            or when.tzinfo is None
                            or when.timestamp()
                            < now.timestamp() - (86400 if kind == "daily" else 3600)
                        ):
                            continue
                        row = {"time": int(when.timestamp())}
                        if kind == "hourly":
                            row["temperature"] = celsius(point["temperature"])
                        else:
                            row.update(
                                low=celsius(point["templow"]), high=celsius(point["temperature"])
                            )
                        if "humidity" in point:
                            row["humidity"] = number(point["humidity"], 0, 100)
                        forecasts[kind].append(row)
                    except (Invalid, KeyError, TypeError, ValueError):
                        self.failures = min(self.failures + 1, 2147483647)
                forecasts[kind].sort(key=lambda row: row["time"])
            return native_weather.payload(
                current,
                forecasts["hourly"],
                forecasts["daily"],
                self.hass.config.time_zone,
                int(now.timestamp()),
            )

    def diagnostics(self):
        return {"configured": self.enabled(), "requests": self.requests, "failures": self.failures}
