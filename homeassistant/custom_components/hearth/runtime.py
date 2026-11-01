"""Push native telemetry directly into Home Assistant; no MQTT dependency."""

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from urllib.parse import urlsplit

from aiohttp import web
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from ._backend import reported_store
from ._backend.api import NATIVE, create_app
from ._backend.core import Core
from ._backend.validation import Invalid
from .const import DOMAIN
from .profile import PreparedProfile

_LOGGER = logging.getLogger(__name__)


class ReportingCore(Core):
    def __init__(self, registry, changed):
        super().__init__(registry)
        self.changed = changed

    def caps(self, ident):
        caps = super().caps(ident)
        modes = list(caps["modes"])
        if {"heat", "cool"} <= set(modes) and "heat_cool" not in modes:
            modes.append("heat_cool")
        if "heat" in modes and "emergency" not in modes:
            modes.append("emergency")
        return {**caps, "modes": modes}

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
            self.core,
            origin=profile.origin,
            native_telemetry=True,
            native_controls=True,
            native_hold_seconds=290,
        )
        self.app[NATIVE].notify = self.changed
        self.app[NATIVE].reported_changed = self.reported_changed
        self.cache_directory = hass.config.path(".storage", DOMAIN)
        self.cache_generation = self.cache_saved_generation = 0
        self.cache_lock = asyncio.Lock()
        self.cache_task = None
        self.cache_errors = {"load_failed": False, "save_failed": False}
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

    @callback
    def reported_changed(self, _ident):
        self.cache_generation += 1

    async def flush_reported(self):
        async with self.cache_lock:
            if self.cache_saved_generation == self.cache_generation:
                return
            generation = self.cache_generation
            try:
                snapshot = self.controls.snapshot_reported()
                await self.hass.async_add_executor_job(
                    reported_store.save, self.cache_directory, snapshot
                )
            except (OSError, Invalid):
                if not self.cache_errors["save_failed"]:
                    _LOGGER.warning("Hearth reported-state cache could not be saved")
                self.cache_errors["save_failed"] = True
                return
            self.cache_errors["save_failed"] = False
            self.cache_saved_generation = generation

    async def start(self):
        try:
            saved = await self.hass.async_add_executor_job(
                reported_store.load, self.cache_directory
            )
            if saved is not None:
                self.controls.restore_reported(saved)
        except (OSError, Invalid):
            self.cache_errors["load_failed"] = True
            _LOGGER.warning(
                "Hearth reported-state cache could not be loaded; waiting for native reports"
            )
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
            if self.cache_generation != self.cache_saved_generation and (
                self.cache_task is None or self.cache_task.done()
            ):
                self.cache_task = self.hass.async_create_background_task(
                    self.flush_reported(), "Hearth reported state cache"
                )
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
        await self.flush_reported()

    @property
    def controls(self):
        return self.app[NATIVE]

    def enqueue(self, ident, body):
        return self.controls.enqueue(ident, body)

    def diagnostics(self):
        return self.app[NATIVE].diagnostics() | {"reported_cache": dict(self.cache_errors)}
