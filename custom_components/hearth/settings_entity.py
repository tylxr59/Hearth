"""Shared reported-only configuration entity behavior."""

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


class SettingEntity:
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def configure(self, runtime, ident, field, spec):
        self.runtime, self.ident, self.field, self.spec = runtime, ident, field, spec
        self._attr_name = spec.label
        self._attr_unique_id = f"hearth_{ident}_setting_{field}"
        self._attr_entity_registry_enabled_default = not spec.equipment
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ident)})

    @property
    def reported(self):
        return (
            self.runtime.controls.reported.get(self.ident, {})
            .get("device", {})
            .get("values", {})
            .get(self.field)
        )

    @property
    def available(self):
        return self.runtime.core.available(self.ident) and self.reported is not None

    @property
    def extra_state_attributes(self):
        cached = ("device", self.field) in self.runtime.controls.restored_fields.get(
            self.ident, set()
        )
        return {
            "reported_state_source": "unknown"
            if self.reported is None
            else "cache"
            if cached
            else "device"
        }

    async def set_value(self, value):
        if self.spec.equipment:
            context = self._context
            user = (
                await self.hass.auth.async_get_user(context.user_id)
                if context and context.user_id
                else None
            )
            if user is None or not user.is_admin:
                raise HomeAssistantError("Equipment configuration requires an HA administrator")
        self.runtime.enqueue(
            self.ident,
            {
                "operation": "device_settings",
                "value": {
                    "settings": {self.field: value},
                    "confirm_equipment_changes": self.spec.equipment,
                },
            },
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        @callback
        def changed():
            self.async_write_ha_state()

        self.async_on_remove(self.runtime.subscribe(self.ident, changed))
