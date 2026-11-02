"""Administrator-only download of this endpoint's commissioning credentials."""

from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .profile import private_read


class HearthCommissioningView(HomeAssistantView):
    url = "/api/hearth/commissioning"
    name = "api:hearth:commissioning"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass

    async def get(self, request):
        if not request["hass_user"].is_admin:
            raise web.HTTPForbidden()
        try:
            data = await self.hass.async_add_executor_job(
                private_read,
                Path(self.hass.config.path(".storage", "hearth", "commissioning.zip")),
                65536,
            )
        except OSError as exc:
            raise web.HTTPNotFound() from exc
        return web.Response(
            body=data,
            content_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="hearth-commissioning.zip"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
