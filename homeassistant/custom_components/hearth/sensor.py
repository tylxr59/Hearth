"""Native reported sensors; preserve values and suggest appropriate display precision."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

SENSORS = (
    ("temperature", "Temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
    ("humidity", "Humidity", SensorDeviceClass.HUMIDITY, PERCENTAGE),
    (
        "target_temperature",
        "Target temperature",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthSensor(runtime, ident, field, name, device_class, unit)
        for ident in runtime.core.registry.data["devices"]
        for field, name, device_class, unit in SENSORS
    )


class HearthSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime, ident, field, name, device_class, unit):
        self.runtime, self.ident, self.field = runtime, ident, field
        self._attr_unique_id = f"hearth_{ident}_{field}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Nest",
            model="Learning Thermostat Gen 2 (experimental)",
            name="Hearth Thermostat",
        )
        if field != "target_temperature":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def suggested_display_precision(self):
        # The native Celsius setpoint may convert to e.g.65.9F while the Nest
        # displays66F. Suggest the dial's display precision, without changing
        # telemetry, history, commands or the user's explicit precision option.
        if self.field == "target_temperature":
            return 0 if self.unit_of_measurement == UnitOfTemperature.FAHRENHEIT else 1
        return None

    @property
    def native_value(self):
        return self.runtime.core.states.get(self.ident, {}).get(self.field)

    @property
    def extra_state_attributes(self):
        return {"reported_state_source": self.runtime.controls.state_source(self.ident, self.field)}

    @property
    def available(self):
        return self.runtime.core.available(self.ident) and self.native_value is not None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def changed():
            self.async_write_ha_state()

        self.async_on_remove(self.runtime.subscribe(self.ident, changed))
