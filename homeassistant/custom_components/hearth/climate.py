"""Local native climate controls; reported state, no HA-side HVAC algorithm."""

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from ._backend.validation import Invalid
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthClimate(runtime, ident) for ident in runtime.core.registry.data["devices"]
    )


class HearthClimate(ClimateEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 10
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5
    # HA's generic turn_on chooses a mode. Require an explicit supported mode.
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, runtime, ident):
        self.runtime, self.ident = runtime, ident
        self._attr_unique_id = f"hearth_{ident}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ident)},
            manufacturer="Nest",
            model="Learning Thermostat Gen 2 (experimental)",
            name="Hearth Thermostat",
        )

    @property
    def available(self):
        return self.runtime.core.available(self.ident)

    @property
    def supported_features(self):
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self.runtime.controls.capabilities(self.ident)["fan"]:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def hvac_modes(self):
        return [HVACMode(m) for m in self.runtime.controls.capabilities(self.ident)["modes"]]

    @property
    def hvac_mode(self):
        mode = self.runtime.core.states.get(self.ident, {}).get("mode")
        return HVACMode(mode) if mode in ("off", "heat", "cool") else None

    @property
    def hvac_action(self):
        value = self.runtime.controls.action(self.ident)
        return HVACAction(value) if value is not None else None

    @property
    def current_temperature(self):
        return self.runtime.core.states.get(self.ident, {}).get("temperature")

    @property
    def target_temperature(self):
        return self.runtime.core.states.get(self.ident, {}).get("target_temperature")

    @property
    def current_humidity(self):
        return self.runtime.core.states.get(self.ident, {}).get("humidity")

    @property
    def fan_modes(self):
        return ["auto", "on"] if self.runtime.controls.capabilities(self.ident)["fan"] else None

    @property
    def fan_mode(self):
        return self.runtime.core.states.get(self.ident, {}).get("fan")

    @property
    def extra_state_attributes(self):
        return {"command_status": self.runtime.controls.command_status(self.ident)}

    def _enqueue(self, operation, value):
        try:
            self.runtime.enqueue(self.ident, {"operation": operation, "value": value})
        except Invalid as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE not in kwargs or set(kwargs) - {ATTR_TEMPERATURE, ATTR_ENTITY_ID}:
            raise HomeAssistantError("A single target temperature is required")
        self._enqueue("temperature", kwargs[ATTR_TEMPERATURE])

    async def async_set_hvac_mode(self, hvac_mode):
        self._enqueue("mode", hvac_mode)

    async def async_set_fan_mode(self, fan_mode):
        self._enqueue("fan", fan_mode)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def changed():
            self.async_write_ha_state()

        self.async_on_remove(self.runtime.subscribe(self.ident, changed))
