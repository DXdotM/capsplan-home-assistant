"""CapsPlan medication reminder — read your CapsPlan data from iCloud."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import CapsPlanClient
from .const import API_TOKEN, CONF_WEB_AUTH_TOKEN, RECOMPUTE_INTERVAL
from .coordinator import CapsPlanConfigEntry, CapsPlanCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CapsPlanConfigEntry) -> bool:
    """Sets up CapsPlan from a config entry."""

    @callback
    def _save_token(token: str) -> None:
        # CloudKit replaces the sign-in token with every answer.
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEB_AUTH_TOKEN: token}
        )

    client = CapsPlanClient(
        async_get_clientsession(hass),
        API_TOKEN,
        entry.data[CONF_WEB_AUTH_TOKEN],
        on_token=_save_token,
    )
    coordinator = CapsPlanCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _recompute(_now) -> None:
        coordinator.refresh_state()

    entry.async_on_unload(async_track_time_interval(hass, _recompute, RECOMPUTE_INTERVAL))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CapsPlanConfigEntry) -> bool:
    """Unloads a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: CapsPlanConfigEntry) -> None:
    """Deletes the locally cached records when the entry is removed."""
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN, STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
