"""Bounded native numeric configuration, with reported values only."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode

from ._backend.device_settings import SETTINGS
from .settings_entity import SettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthSettingNumber(runtime, ident, name, spec)
        for ident in runtime.core.registry.data["devices"]
        for name, spec in SETTINGS.items()
        if spec.kind == "number" and name not in ("hot_water_boost_time_to_end", "time_to_target")
    )


class HearthSettingNumber(SettingEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime, ident, field, spec):
        self.configure(runtime, ident, field, spec)
        self._attr_native_min_value, self._attr_native_max_value = spec.low, spec.high
        self._attr_native_step = (
            1
            if field
            in (
                "target_humidity",
                "fan_timer_duration_minutes",
                "fan_duty_cycle",
                "fan_duty_start_time",
                "fan_duty_end_time",
                "time_to_target",
                "filter_reminder_level",
            )
            else 0.5
        )
        if "temp" in field or "threshold" in field:
            self._attr_native_unit_of_measurement = "°C"
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        elif field == "target_humidity":
            self._attr_native_unit_of_measurement = "%"
            self._attr_device_class = NumberDeviceClass.HUMIDITY

    @property
    def native_value(self):
        return self.reported

    async def async_set_native_value(self, value):
        await self.set_value(value)
