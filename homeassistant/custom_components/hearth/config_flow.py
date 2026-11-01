"""Import a local commissioning profile; no credentials in UI fields or entries."""

from pathlib import Path

from homeassistant import config_entries

from .const import DOMAIN
from .profile import PROFILE_ERRORS, load_profile


class HearthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("hearth-native-endpoint")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    load_profile, Path(self.hass.config.path(".storage", DOMAIN))
                )
            except PROFILE_ERRORS:
                errors["base"] = "profile_not_ready"
            else:
                return self.async_create_entry(title="Hearth", data={})
        return self.async_show_form(step_id="user", errors=errors)
