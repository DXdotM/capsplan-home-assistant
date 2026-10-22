"""Config flow for CapsPlan: sign in with the Apple ID that syncs CapsPlan."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import CapsPlanAuthError, CapsPlanClient, CapsPlanError
from .const import (
    API_TOKEN,
    CONF_HIDE_NAMES,
    CONF_PERSON,
    CONF_USER_RECORD,
    CONF_WEB_AUTH_TOKEN,
    DOMAIN,
    SIGN_IN_URL,
)

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WEB_AUTH_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)
USER_SCHEMA = TOKEN_SCHEMA.extend({vol.Optional(CONF_PERSON, default=""): TextSelector()})


def entry_title(person: str) -> str:
    return f"CapsPlan {person}" if person else "CapsPlan"


class CapsPlanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Signs in to iCloud via the CapsPlan sign-in page."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CapsPlanOptionsFlow:
        return CapsPlanOptionsFlow()

    async def _validate(self, token: str) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Checks the pasted token; returns errors or the entry data."""
        latest = {"token": token.strip()}

        def remember(new: str) -> None:
            latest["token"] = new

        client = CapsPlanClient(
            async_get_clientsession(self.hass), API_TOKEN, latest["token"], on_token=remember
        )
        try:
            user = await client.current_user()
            # Also proves that CapsPlan's sync data is readable.
            await client.zone_changes(None)
        except CapsPlanAuthError:
            return {"base": "invalid_auth"}, None
        except CapsPlanError:
            return {"base": "cannot_connect"}, None
        return {}, {CONF_WEB_AUTH_TOKEN: latest["token"], CONF_USER_RECORD: user}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, data = await self._validate(user_input[CONF_WEB_AUTH_TOKEN])
            if data is not None:
                await self.async_set_unique_id(data[CONF_USER_RECORD])
                self._abort_if_unique_id_configured()
                person = user_input.get(CONF_PERSON, "").strip()
                return self.async_create_entry(
                    title=entry_title(person), data=data, options={CONF_PERSON: person}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
            description_placeholders={"sign_in_url": SIGN_IN_URL},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors, data = await self._validate(user_input[CONF_WEB_AUTH_TOKEN])
            if data is not None:
                await self.async_set_unique_id(data[CONF_USER_RECORD])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"sign_in_url": SIGN_IN_URL},
        )


class CapsPlanOptionsFlow(OptionsFlowWithReload):
    """Changes whose CapsPlan this is."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            person = user_input.get(CONF_PERSON, "").strip()
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=entry_title(person)
            )
            return self.async_create_entry(
                data={CONF_PERSON: person, CONF_HIDE_NAMES: user_input.get(CONF_HIDE_NAMES, False)}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_PERSON, default=""): TextSelector(),
                        vol.Optional(CONF_HIDE_NAMES, default=False): BooleanSelector(),
                    }
                ),
                self.config_entry.options,
            ),
        )
