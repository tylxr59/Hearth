"""Import a local commissioning profile; no credentials in UI fields or entries."""

from pathlib import Path

import voluptuous as vol
from homeassistant.core import callback

from homeassistant import config_entries

from .const import DOMAIN
from .profile import PROFILE_ERRORS, load_profile


class HearthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HearthOptionsFlow()

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


class HearthOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        choices = {"disabled": "Disabled", "auto": "Use the only HA weather entity"}
        choices.update(
            {
                entity: self.hass.states.get(entity).name
                for entity in self.hass.states.async_entity_ids("weather")
            }
        )
        errors = {}
        if user_input is not None:
            selected = user_input["weather_entity"]
            if selected not in choices:
                errors["base"] = "weather_not_found"
            else:
                return self.async_create_entry(
                    title="", data={} if selected == "auto" else {"weather_entity": selected}
                )
        selected = self.config_entry.options.get("weather_entity", "auto")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "weather_entity", default=selected if selected in choices else "disabled"
                    ): vol.In(choices)
                }
            ),
            errors=errors,
        )
