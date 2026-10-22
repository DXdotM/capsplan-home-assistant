"""Config flow for CapsPlan: sign in with the Apple ID that syncs CapsPlan."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import CapsPlanAuthError, CapsPlanClient, CapsPlanError
from .const import API_TOKEN, CONF_USER_RECORD, CONF_WEB_AUTH_TOKEN, DOMAIN, SIGN_IN_URL

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_WEB_AUTH_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


class CapsPlanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Signs in to iCloud via the CapsPlan sign-in page."""

    VERSION = 1

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
                return self.async_create_entry(title="CapsPlan", data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=TOKEN_SCHEMA,
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
