"""Optional reported maintenance and native activity flags."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .settings_entity import SettingEntity


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        HearthDiagnosticFlag(runtime, ident, field, label, cls)
        for ident in runtime.core.registry.data["devices"]
        for field, label, cls in (
            (
                "filter_replacement_needed",
                "Filter replacement needed",
                BinarySensorDeviceClass.PROBLEM,
            ),
            ("sunlight_correction_active", "Sunblock active", None),
            ("preconditioning_active", "Early-On active", None),
            ("heatpump_ready", "Heat pump ready", None),
        )
    )


class HearthDiagnosticFlag(SettingEntity, BinarySensorEntity):
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, ident, field, label, device_class):
        self.runtime, self.ident, self.field = runtime, ident, field
        self._attr_name = label
        self._attr_unique_id = f"hearth_{ident}_diagnostic_{field}"
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, ident)})

    @property
    def is_on(self):
        return self.reported
