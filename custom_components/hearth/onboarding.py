"""Suggest HA's own private addresses without discovering or contacting devices."""

from homeassistant.components import network
from homeassistant.helpers.network import NoURLAvailableError, get_url

from ._backend.onboarding import candidate_origins


async def async_origins(hass):
    adapters = await network.async_get_adapters(hass)
    try:
        internal = get_url(hass, allow_external=False, allow_cloud=False, allow_ip=True)
    except NoURLAvailableError:
        internal = None
    return candidate_origins(adapters, internal)
