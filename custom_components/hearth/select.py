"""Enumerated native display and fan configuration."""

from homeassistant.components.select import SelectEntity

from ._backend.device_settings import SETTINGS
from .settings_entity import SettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthSettingSelect(runtime, ident, name, spec)
        for ident in runtime.core.registry.data["devices"]
        for name, spec in SETTINGS.items()
        if spec.kind == "select"
    )


class HearthSettingSelect(SettingEntity, SelectEntity):
    def __init__(self, runtime, ident, field, spec):
        self.configure(runtime, ident, field, spec)
        self._attr_options = list(spec.options)

    @property
    def current_option(self):
        return self.reported

    async def async_select_option(self, option):
        await self.set_value(option)
