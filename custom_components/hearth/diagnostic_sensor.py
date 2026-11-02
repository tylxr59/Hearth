"""Optional native diagnostics; values are reported, not inferred equipment state."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .settings_entity import SettingEntity

DIAGNOSTICS = (
    ("battery_level", "Battery voltage", SensorDeviceClass.VOLTAGE, "V"),
    ("rssi", "Wi-Fi signal", SensorDeviceClass.SIGNAL_STRENGTH, "dBm"),
    ("filter_runtime_sec", "Filter runtime", SensorDeviceClass.DURATION, "s"),
    ("time_to_target", "Time to target", SensorDeviceClass.DURATION, "min"),
    ("outdoor_temperature", "Outdoor temperature", SensorDeviceClass.TEMPERATURE, "°C"),
)


class HearthDiagnosticSensor(SettingEntity, SensorEntity):
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, ident, field, label, device_class, unit):
        # Diagnostics intentionally do not have writable Setting specifications.
        self.runtime, self.ident, self.field = runtime, ident, field
        self._attr_name = label
        self._attr_unique_id = f"hearth_{ident}_diagnostic_{field}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        from homeassistant.helpers.device_registry import DeviceInfo

        from .const import DOMAIN

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ident)})

    @property
    def native_value(self):
        value = self.reported
        if self.field == "outdoor_temperature" and value is None:
            value = (
                self.runtime.controls.reported.get(self.ident, {})
                .get("device", {})
                .get("values", {})
                .get("outside_temperature")
            )
        if value is None:
            return None
        if self.field == "rssi":
            return -abs(value)
        if self.field == "time_to_target":
            return max(0, (value - self.runtime.controls.clock()) / 60) if value else 0
        return value

    @property
    def extra_state_attributes(self):
        field = (
            "outside_temperature"
            if self.field == "outdoor_temperature" and self.reported is None
            else self.field
        )
        cached = ("device", field) in self.runtime.controls.restored_fields.get(self.ident, set())
        return {
            "reported_state_source": "unknown"
            if self.native_value is None
            else "cache"
            if cached
            else "device"
        }

    @property
    def available(self):
        return self.runtime.core.available(self.ident) and self.native_value is not None
