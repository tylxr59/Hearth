"""Scoped HA actions for native eco limits and full weekly schedules."""

import copy

import voluptuous as vol
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_conversion import TemperatureConverter

from ._backend import native_features, schedule_backup
from ._backend.validation import Invalid
from .const import DOMAIN


def register(hass, entry):
    runtime = entry.runtime_data

    def identity(entity_id):
        row = er.async_get(hass).async_get(entity_id)
        if row is not None and row.config_entry_id == entry.entry_id and row.platform == DOMAIN:
            for ident in runtime.core.registry.data["devices"]:
                if row.unique_id == f"hearth_{ident}_climate":
                    return ident
        raise HomeAssistantError("Choose a Hearth thermostat climate entity")

    def revision(ident):
        record = runtime.controls._records_for(ident).get(f"schedule.{ident}")
        if record is None:
            raise Invalid("No reported weekly schedule available yet")
        return record.revision

    async def get_schedule(call):
        ident = identity(call.data["entity_id"])
        try:
            week = native_features.schedule(
                runtime.controls.reported.get(ident, {}).get("schedule", {}).get("values", {})
            )
            return {
                "schedule": week,
                "temperature_unit": "°C",
                "revision": revision(ident),
                "source": "cache"
                if any(
                    kind == "schedule"
                    for kind, _ in runtime.controls.restored_fields.get(ident, set())
                )
                else "device",
            }
        except Invalid as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def set_schedule(call):
        ident = identity(call.data["entity_id"])
        week = copy.deepcopy(call.data["schedule"])
        try:
            if call.data["temperature_unit"] == "°F":
                # Validate shape before walking it; bounds are checked after conversion.
                if not isinstance(week.get("days"), dict):
                    raise Invalid("weekly days required")
                for points in week["days"].values():
                    if isinstance(points, dict):
                        points = points.values()
                    elif not isinstance(points, list):
                        raise Invalid("schedule points required")
                    for point in points:
                        if not isinstance(point, dict):
                            raise Invalid("schedule point required")
                        for key in ("temp", "temp-min", "temp-max"):
                            if key in point:
                                value = point[key]
                                if type(value) not in (int, float):
                                    raise Invalid("numeric schedule temperature required")
                                point[key] = TemperatureConverter.convert(value, "°F", "°C")
            week = native_features.schedule(week)
            body = {
                "operation": "schedule",
                "value": week,
                "expected_revision": call.data["expected_revision"],
            }
            # Check before disk I/O, then again after the backup has been synced.
            runtime.controls.advanced_plan(ident, body, True)
            previous = copy.deepcopy(runtime.controls.reported[ident]["schedule"]["values"])
            generation = runtime.core.registry.data["devices"][ident]["hash"]
            await hass.async_add_executor_job(
                schedule_backup.archive,
                runtime.cache_directory,
                ident,
                generation,
                call.data["expected_revision"],
                previous,
            )
            if runtime.core.registry.data["devices"].get(ident, {}).get("hash") != generation:
                raise Invalid("device enrollment changed during backup")
            runtime.controls.enqueue(ident, body, schedule_backed_up=True)
        except (Invalid, OSError, ValueError) as exc:
            raise HomeAssistantError("Schedule not queued: " + str(exc)) from exc

    async def eco_limits(call):
        ident = identity(call.data["entity_id"])
        values = {name: call.data[name] for name in ("low", "high")}
        if call.data["temperature_unit"] == "°F":
            values = {
                key: TemperatureConverter.convert(value, "°F", "°C")
                for key, value in values.items()
            }
        try:
            runtime.enqueue(ident, {"operation": "eco_temperatures", "value": values})
        except Invalid as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def schedule_mode(call):
        ident = identity(call.data["entity_id"])
        try:
            runtime.enqueue(ident, {"operation": "schedule_mode", "value": call.data["mode"]})
        except Invalid as exc:
            raise HomeAssistantError(str(exc)) from exc

    def strict_revision(value):
        if type(value) is not int or not 0 <= value <= (1 << 53) - 1:
            raise vol.Invalid("nonnegative integer revision required")
        return value

    target = {vol.Required("entity_id"): cv.entity_id}
    handlers = {
        "get_schedule": (get_schedule, vol.Schema(target), SupportsResponse.ONLY),
        "set_schedule": (
            set_schedule,
            vol.Schema(
                target
                | {
                    vol.Required("schedule"): dict,
                    vol.Required("expected_revision"): strict_revision,
                    vol.Required("temperature_unit"): vol.In(("°C", "°F")),
                }
            ),
            SupportsResponse.NONE,
        ),
        "set_schedule_mode": (
            schedule_mode,
            vol.Schema(target | {vol.Required("mode"): vol.In(tuple(native_features.MODES))}),
            SupportsResponse.NONE,
        ),
        "set_eco_temperatures": (
            eco_limits,
            vol.Schema(
                target
                | {
                    vol.Required("low"): vol.All(vol.Coerce(float), vol.Range(min=10, max=86)),
                    vol.Required("high"): vol.All(vol.Coerce(float), vol.Range(min=10, max=86)),
                    vol.Required("temperature_unit"): vol.In(("°C", "°F")),
                }
            ),
            SupportsResponse.NONE,
        ),
    }
    for name, (handler, schema, response) in handlers.items():
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=response
        )

    @callback
    def remove_services():
        for name in handlers:
            hass.services.async_remove(DOMAIN, name)

    entry.async_on_unload(remove_services)
