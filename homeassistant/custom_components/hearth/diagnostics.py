"""Payload-free integration diagnostics: no identifiers, addresses or readings."""


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    return runtime.diagnostics() | {
        "devices": [
            {
                "available": runtime.core.available(ident),
                "controls": runtime.controls.control_view(ident),
            }
            for ident in runtime.core.registry.data["devices"]
        ]
    }
