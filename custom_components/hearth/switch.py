"""Native learning, comfort and equipment configuration switches."""

from homeassistant.components.switch import SwitchEntity

from ._backend.device_settings import SETTINGS
from .settings_entity import SettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthSettingSwitch(runtime, ident, name, spec)
        for ident in runtime.core.registry.data["devices"]
        for name, spec in SETTINGS.items()
        if spec.kind == "boolean" and name != "preconditioning_active"
    )


class HearthSettingSwitch(SettingEntity, SwitchEntity):
    def __init__(self, runtime, ident, field, spec):
        self.configure(runtime, ident, field, spec)

    @property
    def is_on(self):
        return self.reported

    async def async_turn_on(self, **kwargs):
        await self.set_value(True)

    async def async_turn_off(self, **kwargs):
        await self.set_value(False)
