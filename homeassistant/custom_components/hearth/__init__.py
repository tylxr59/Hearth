"""Hearth native HTTPS receiver and local Home Assistant entities."""

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .probe import HearthConnectivityView
from .profile import load_profile
from .runtime import HearthRuntime
from .services import register as register_services

PLATFORMS = [Platform.SENSOR, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    try:
        profile = await hass.async_add_executor_job(
            load_profile, Path(hass.config.path(".storage", DOMAIN))
        )
        runtime = HearthRuntime(hass, profile, entry)
        await runtime.start()
    except Exception as exc:
        raise ConfigEntryNotReady("Hearth profile or TLS listener is not ready") from exc
    entry.runtime_data = runtime
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        hass.data[DOMAIN] = runtime
        register_services(hass, entry)
        if not hass.data.get(DOMAIN + "_probe_registered"):
            hass.http.register_view(HearthConnectivityView(hass))
            hass.data[DOMAIN + "_probe_registered"] = True
    except Exception:
        hass.data.pop(DOMAIN, None)
        await runtime.stop()
        raise

    async def stop(_event):
        hass.data.pop(DOMAIN, None)
        await runtime.stop()

    async def options_updated(hass, entry):
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(options_updated))
    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.stop()
    hass.data.pop(DOMAIN, None)
    return True
