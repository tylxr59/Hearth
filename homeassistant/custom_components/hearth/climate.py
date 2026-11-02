"""Local native climate controls; reported state, no HA-side HVAC algorithm."""

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW
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
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            if self.hvac_mode == HVACMode.HEAT_COOL
            else ClimateEntityFeature.TARGET_TEMPERATURE
        )
        if self.runtime.controls.capabilities(self.ident)["fan"]:
            features |= ClimateEntityFeature.FAN_MODE
        if self.preset_modes:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def hvac_modes(self):
        return [
            HVACMode(m)
            for m in self.runtime.controls.capabilities(self.ident)["modes"]
            if m in ("off", "heat", "cool", "heat_cool")
        ]

    @property
    def hvac_mode(self):
        mode = self.runtime.core.states.get(self.ident, {}).get("mode")
        return HVACMode(mode) if mode in ("off", "heat", "cool", "heat_cool") else None

    @property
    def hvac_action(self):
        value = self.runtime.controls.action(self.ident)
        return HVACAction(value) if value is not None else None

    @property
    def current_temperature(self):
        return self.runtime.core.states.get(self.ident, {}).get("temperature")

    @property
    def target_temperature(self):
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return None
        return self.runtime.core.states.get(self.ident, {}).get("target_temperature")

    def range_target(self, field):
        values = (
            self.runtime.controls.reported.get(self.ident, {}).get("shared", {}).get("values", {})
        )
        low = values.get("target_temperature_low")
        high = values.get("target_temperature_high")
        if (
            self.hvac_mode != HVACMode.HEAT_COOL
            or type(low) not in (int, float)
            or type(high) not in (int, float)
            or low >= high
        ):
            return None
        return values[field]

    @property
    def target_temperature_low(self):
        return self.range_target("target_temperature_low")

    @property
    def target_temperature_high(self):
        return self.range_target("target_temperature_high")

    @property
    def current_humidity(self):
        return self.runtime.core.states.get(self.ident, {}).get("humidity")

    @property
    def preset_modes(self):
        presets = ["none"]
        native = self.runtime.controls
        home = native.home_key(self.ident)
        record = native._records_for(self.ident).get(home)
        eco = native.reported.get(self.ident, {}).get("structure", {}).get("values", {})
        if (
            record is not None
            and type(eco.get("manual_eco_all")) is bool
            and type(eco.get("manual_eco_timestamp")) is int
        ):
            presets.append("eco")
        if "emergency" in native.capabilities(self.ident)["modes"]:
            presets.append("emergency_heat")
        return presets if len(presets) > 1 else None

    @property
    def preset_mode(self):
        if not self.preset_modes:
            return None
        eco = (
            self.runtime.controls.reported.get(self.ident, {})
            .get("structure", {})
            .get("values", {})
            .get("manual_eco_all")
        )
        if eco is True:
            return "eco"
        mode = (
            self.runtime.controls.reported.get(self.ident, {})
            .get("shared", {})
            .get("values", {})
            .get("target_temperature_type")
        )
        if mode is None:
            return None
        return "emergency_heat" if mode == "emergency" else "none"

    @property
    def fan_modes(self):
        return ["auto", "on"] if self.runtime.controls.capabilities(self.ident)["fan"] else None

    @property
    def fan_mode(self):
        return self.runtime.core.states.get(self.ident, {}).get("fan")

    @property
    def extra_state_attributes(self):
        return {
            "command_status": self.runtime.controls.command_status(self.ident),
            "reported_state_source": {
                field: self.runtime.controls.state_source(self.ident, field)
                for field in (
                    "temperature",
                    "target_temperature",
                    "target_temperature_low",
                    "target_temperature_high",
                    "mode",
                    "fan",
                )
            },
        }

    def _enqueue(self, operation, value):
        try:
            self.runtime.enqueue(self.ident, {"operation": operation, "value": value})
        except Invalid as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def async_set_temperature(self, **kwargs):
        fields = set(kwargs) - {ATTR_ENTITY_ID}
        if fields == {ATTR_TEMPERATURE}:
            self._enqueue("temperature", kwargs[ATTR_TEMPERATURE])
        elif fields == {ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH}:
            self._enqueue(
                "temperature_range",
                {"low": kwargs[ATTR_TARGET_TEMP_LOW], "high": kwargs[ATTR_TARGET_TEMP_HIGH]},
            )
        else:
            raise HomeAssistantError("Provide a single target or both range targets")

    async def async_set_hvac_mode(self, hvac_mode):
        self._enqueue("mode", hvac_mode)

    async def async_set_preset_mode(self, preset_mode):
        if not self.preset_modes or preset_mode not in self.preset_modes:
            raise HomeAssistantError("Unsupported preset")
        if preset_mode == "eco":
            self._enqueue("eco", True)
        elif self.preset_mode == "eco":
            if preset_mode != "none":
                raise HomeAssistantError("Clear eco before requesting emergency heat")
            if ("structure", "manual_eco_all") in self.runtime.controls.restored_fields.get(
                self.ident, set()
            ):
                raise HomeAssistantError("A fresh eco report is required to clear eco")
            self._enqueue("eco", False)
        elif preset_mode == "emergency_heat":
            self._enqueue("mode", "emergency")
        elif self.runtime.controls.state_source(self.ident, "mode") != "device":
            raise HomeAssistantError(
                "A fresh device mode report is required to clear emergency heat"
            )
        elif self.preset_mode == "emergency_heat":
            self._enqueue("mode", "heat")

    async def async_set_fan_mode(self, fan_mode):
        self._enqueue("fan", fan_mode)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def changed():
            self.async_write_ha_state()

        self.async_on_remove(self.runtime.subscribe(self.ident, changed))
