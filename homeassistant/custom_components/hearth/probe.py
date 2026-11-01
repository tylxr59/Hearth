"""Bodyless local connectivity response, separate from the authenticated transport."""

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN


class HearthConnectivityView(HomeAssistantView):
    url = "/api/h/204"
    name = "api:hearth:connectivity"
    requires_auth = False

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        if request.query_string or request.can_read_body:
            return web.Response(status=400)
        runtime = self.hass.data.get(DOMAIN)
        if runtime is None or runtime.runner is None:
            return web.Response(status=503)
        return web.Response(status=204, headers={"Cache-Control": "no-store"})
