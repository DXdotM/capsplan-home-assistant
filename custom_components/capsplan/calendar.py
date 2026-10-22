"""Calendar with all planned CapsPlan doses."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import logic
from .coordinator import CapsPlanConfigEntry, CapsPlanCoordinator
from .entity import CapsPlanEntity

PARALLEL_UPDATES = 0

# How long a dose appears in the calendar.
DURATION = timedelta(minutes=15)
# Longest range one query computes (a month view plus some margin).
MAX_DAYS = 62

MARKS = {"taken": "✓ ", "skipped": "✗ ", "open": "⏰ ", "upcoming": ""}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CapsPlanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CapsPlanCalendar(entry.runtime_data)])


def _event(state: logic.MedicationState, dose: logic.PlannedDose) -> CalendarEvent:
    med = state.medication
    lines = [logic.dose_label(med, dose.dose)]
    if dose.confirmed_at is not None:
        lines.append(f"✓ {dose.confirmed_at.strftime('%H:%M')}")
    return CalendarEvent(
        start=dose.time,
        end=dose.time + DURATION,
        summary=MARKS.get(dose.status, "") + logic.dose_label(med, dose.dose),
        description="\n".join(lines),
        uid=f"{med.sid}-{dose.time.isoformat()}",
    )


class CapsPlanCalendar(CapsPlanEntity, CalendarEntity):
    """Every planned dose as an event: taken ✓, skipped ✗, open ⏰."""

    def __init__(self, coordinator: CapsPlanCoordinator) -> None:
        super().__init__(coordinator, "doses")

    @property
    def event(self) -> CalendarEvent | None:
        """The open dose that is due longest, else the next dose."""
        data = self.coordinator.data
        if data.open_list:
            return _event(*data.open_list[0])
        if data.next_dose is not None:
            return _event(*data.next_dose)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        data = self.coordinator.data
        tz = dt_util.get_default_time_zone()
        first = start_date.astimezone(tz).date()
        last = min(end_date.astimezone(tz).date(), first + timedelta(days=MAX_DAYS))
        events: list[CalendarEvent] = []
        day = first
        while day <= last:
            for state in data.medications.values():
                for dose in logic.planned_doses(state.medication, day, data.now):
                    if start_date <= dose.time < end_date:
                        events.append(_event(state, dose))
            day += timedelta(days=1)
        events.sort(key=lambda e: (e.start, e.summary))
        return events
