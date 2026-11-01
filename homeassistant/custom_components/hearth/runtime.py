"""Push native telemetry directly into Home Assistant; no MQTT dependency."""

from collections.abc import Callable
from datetime import timedelta
from urllib.parse import urlsplit

from aiohttp import web
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from ._backend.api import NATIVE, create_app
from ._backend.core import Core
from .profile import PreparedProfile


class ReportingCore(Core):
    def __init__(self, registry, changed):
        super().__init__(registry)
        self.changed = changed

    def report(self, ident, data):
        super().report(ident, data)
        self.changed(ident)


class HearthRuntime:
    def __init__(self, hass: HomeAssistant, profile: PreparedProfile):
        self.hass = hass
        self.profile = profile
        self.listeners: dict[str, set[Callable[[], None]]] = {}
        self.core = ReportingCore(profile.registry, self.changed)
        self.app = create_app(
            self.core, origin=profile.origin, native_telemetry=True, native_controls=True
        )
        self.app[NATIVE].notify = self.changed
        self.runner: web.AppRunner | None = None
        self.cancel_timer: Callable[[], None] | None = None

    @callback
    def changed(self, ident):
        for listener in tuple(self.listeners.get(ident, ())):
            listener()

    @callback
    def subscribe(self, ident, listener):
        listeners = self.listeners.setdefault(ident, set())
        listeners.add(listener)

        @callback
        def remove():
            listeners.discard(listener)

        return remove

    async def start(self):
        runner = web.AppRunner(self.app, access_log=None)
        self.runner = runner
        try:
            await runner.setup()
            # Dedicated TLS listener; native firmware does not speak HA's API.
            site = web.TCPSite(
                runner,
                "0.0.0.0",  # nosec B104
                urlsplit(self.profile.origin).port,
                ssl_context=self.profile.context,
            )
            await site.start()
        except Exception:
            await self.stop()
            raise

        @callback
        def expire_availability(_now):
            for ident in tuple(self.listeners):
                self.changed(ident)

        self.cancel_timer = async_track_time_interval(
            self.hass, expire_availability, timedelta(seconds=15)
        )

    async def stop(self):
        if self.cancel_timer:
            self.cancel_timer()
            self.cancel_timer = None
        if self.runner:
            runner, self.runner = self.runner, None
            await runner.cleanup()

    @property
    def controls(self):
        return self.app[NATIVE]

    def enqueue(self, ident, body):
        return self.controls.enqueue(ident, body)

    def diagnostics(self):
        return self.app[NATIVE].diagnostics()
