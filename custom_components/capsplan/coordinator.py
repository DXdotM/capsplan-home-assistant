"""Keeps CapsPlan's data in Home Assistant up to date."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import logic
from .api import CapsPlanAuthError, CapsPlanClient, CapsPlanError
from .const import (
    CONF_HIDE_NAMES,
    DOMAIN,
    MEDICATION_WORD,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type CapsPlanConfigEntry = ConfigEntry[CapsPlanCoordinator]


@dataclass
class CapsPlanData:
    """Everything the entities show, computed for one point in time."""

    now: datetime
    medications: dict[str, logic.MedicationState]
    open_doses: int
    next_dose: tuple[logic.MedicationState, logic.PlannedDose] | None
    # All doses due at the next dose time (several medications at 08:00).
    next_group: list[tuple[logic.MedicationState, logic.PlannedDose]]
    open_list: list[tuple[logic.MedicationState, logic.PlannedDose]]
    # Today's doses not taken or skipped yet: open (due) and upcoming.
    remaining_today: list[tuple[logic.MedicationState, logic.PlannedDose]]
    adherence_7d: float | None
    last_sync: datetime | None


class CapsPlanCoordinator(DataUpdateCoordinator[CapsPlanData]):
    """Fetches changes from iCloud every few minutes and recomputes the
    schedule state (open, next dose, ...) every minute in between."""

    config_entry: CapsPlanConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CapsPlanConfigEntry, client: CapsPlanClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._sync = logic.SyncStore()
        self._loaded = False
        self._last_sync: datetime | None = None
        # Medications built from the records; rebuilt only when they change.
        self._meds: dict[str, logic.Medication] = {}
        self._built = False

    async def _async_update_data(self) -> CapsPlanData:
        if not self._loaded:
            self._sync = logic.SyncStore.from_dict(await self._store.async_load())
            self._loaded = True
        try:
            try:
                records, token = await self.client.zone_changes(self._sync.sync_token)
            except CapsPlanAuthError:
                raise
            except CapsPlanError:
                if self._sync.sync_token is None:
                    raise
                # The change token may have expired: start over with everything.
                _LOGGER.debug("Incremental fetch failed, fetching all records again")
                self._sync = logic.SyncStore()
                records, token = await self.client.zone_changes(None)
        except CapsPlanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CapsPlanError as err:
            raise UpdateFailed(str(err)) from err

        changed = self._sync.apply(records)
        if changed or token != self._sync.sync_token:
            self._sync.sync_token = token
            self._store.async_delay_save(self._sync.to_dict, 10)
        if changed or not self._built:
            self._rebuild()
        self._last_sync = dt_util.utcnow()
        return await self.hass.async_add_executor_job(self._compute, self._meds, self._last_sync)

    def _rebuild(self) -> None:
        """Builds the medications from the synced records (event loop; only
        when records changed). The minute refresh only reads the result."""
        tz = dt_util.get_default_time_zone()
        # Paused or finished medications (switched off in the app) are left out.
        meds = {sid: m for sid, m in logic.build(self._sync, tz).items() if m.active}
        if self.config_entry.options.get(CONF_HIDE_NAMES):
            label = MEDICATION_WORD.get(self.hass.config.language.split("-")[0], "Medication")
            far = dt_util.now()
            ordered = sorted(meds.values(), key=lambda m: (m.created_at or far, m.sid))
            for i, med in enumerate(ordered, 1):
                med.name = f"{label} {i}"
        self._meds = meds
        self._built = True

    @staticmethod
    def _compute(meds: dict[str, logic.Medication], last_sync: datetime | None) -> CapsPlanData:
        """All states for the current time. Runs in the executor: it only
        reads the already built medications, which are never changed after
        _rebuild (a rebuild replaces the whole dict)."""
        now = dt_util.now()
        states = {sid: logic.medication_state(m, now) for sid, m in meds.items()}

        def by_time(x: tuple[logic.MedicationState, logic.PlannedDose]):
            return (x[1].time, x[0].medication.name.lower())

        upcoming = sorted(
            ((s, s.next_dose) for s in states.values() if s.next_dose is not None), key=by_time
        )
        next_group = [x for x in upcoming if x[1].time == upcoming[0][1].time] if upcoming else []
        open_list = sorted(((s, d) for s in states.values() for d in s.overdue), key=by_time)
        remaining_today = open_list + sorted(
            ((s, d) for s in states.values() for d in s.today if d.status == "upcoming"),
            key=by_time,
        )
        scheduled = [m for m in meds.values() if not m.on_demand]
        return CapsPlanData(
            now=now,
            medications=states,
            open_doses=len(open_list),
            next_dose=next_group[0] if next_group else None,
            next_group=next_group,
            open_list=open_list,
            remaining_today=remaining_today,
            adherence_7d=logic.adherence(scheduled, now),
            last_sync=last_sync,
        )

    async def async_refresh_state(self) -> None:
        """Pushes freshly computed states without contacting iCloud.

        Not async_set_updated_data: that would also postpone the next fetch
        from iCloud every time, so it would never happen.
        """
        if self.data is None or not self.last_update_success:
            return
        self.data = await self.hass.async_add_executor_job(
            self._compute, self._meds, self._last_sync
        )
        self.async_update_listeners()
