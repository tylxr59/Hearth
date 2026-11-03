"""Import a local commissioning profile; no credentials in UI fields or entries."""

from pathlib import Path

import voluptuous as vol
from homeassistant.core import callback
from homeassistant.helpers import selector

from homeassistant import config_entries

from ._backend.commissioning import create_profile
from ._backend.native_weather import query_location
from ._backend.validation import Invalid
from .const import DOMAIN
from .onboarding import async_origins
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
        directory = Path(self.hass.config.path(".storage", DOMAIN))
        existing = directory.exists()
        if user_input is not None:
            try:
                if not existing:
                    await self.hass.async_add_executor_job(
                        create_profile, directory, user_input["origin"], user_input["device_id"]
                    )
                await self.hass.async_add_executor_job(load_profile, directory)
            except (*PROFILE_ERRORS, KeyError):
                errors["base"] = "profile_not_ready"
            else:
                return self.async_create_entry(title="Hearth", data={})
        origins = [] if existing else await async_origins(self.hass)
        origin_field = vol.Required("origin")
        selected = (user_input or {}).get("origin") or (origins[0] if len(origins) == 1 else None)
        if selected:
            origin_field = vol.Required("origin", default=selected)
        schema = (
            vol.Schema({})
            if existing
            else vol.Schema(
                {
                    origin_field: selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=origins,
                            custom_value=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                    if origins
                    else str,
                    vol.Required("device_id"): str,
                }
            )
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


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
            postal = user_input.get("weather_postal_code", "").strip()
            country = user_input.get("weather_country_code", "").strip()
            if selected not in choices:
                errors["base"] = "weather_not_found"
            else:
                try:
                    location = (
                        query_location("ipv4", {"zip": postal, "country": country})
                        if postal or country
                        else None
                    )
                except Invalid:
                    errors["base"] = "weather_location_invalid"
                else:
                    data = {} if selected == "auto" else {"weather_entity": selected}
                    if location:
                        data.update(
                            weather_postal_code=location["zip"],
                            weather_country_code=location["country"],
                        )
                    return self.async_create_entry(title="", data=data)
        selected = self.config_entry.options.get("weather_entity", "auto")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "weather_entity", default=selected if selected in choices else "disabled"
                    ): vol.In(choices),
                    vol.Optional(
                        "weather_postal_code",
                        default=self.config_entry.options.get("weather_postal_code", ""),
                    ): str,
                    vol.Optional(
                        "weather_country_code",
                        default=self.config_entry.options.get("weather_country_code", ""),
                    ): str,
                }
            ),
            errors=errors,
        )
