"""CapsPlan data model and schedule logic.

Independent of Home Assistant so it can be tested on its own.

CapsPlan's iCloud sync stores every entity (medication, intake, strength,
...) as one record in the private CloudKit zone "CapsPlanSync". Each record
carries three fields: ``collection``, ``payload`` (the entity as JSON) and
``deleted``. References between entities are sync ids: ``_med`` points at a
medication, ``_strength`` (inside an intake's portions) at a strength. Dates
are microseconds since the Unix epoch; enums are stored as their index.

The schedule functions mirror the app (lib/core/utils/date_utils.dart,
lib/domain/services/tapering_service.dart and HomeViewModel._slotsOnDay):
planned doses are not stored, the app derives them from the schedule, and
only confirmed, skipped or snoozed doses exist as intake records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

# Enum indexes as stored by the app.
STATUS_PENDING, STATUS_CONFIRMED, STATUS_SKIPPED, STATUS_SNOOZED = 0, 1, 2, 3
DIRECTION_DECREASING, DIRECTION_INCREASING = 0, 1
MEDICATION_TYPES = (
    "tablet",
    "liquid",
    "drops",
    "capsule",
    "injection",
    "patch",
    "inhaler",
    "powder",
    "spray",
)

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def from_micros(value: int | None, tz: tzinfo) -> datetime | None:
    """Converts an Isar timestamp (µs since epoch) to an aware local time."""
    if value is None:
        return None
    return (_EPOCH + timedelta(microseconds=value)).astimezone(tz)


def _is_set(value: datetime | None) -> bool:
    """The app's "unset" dates are 1 Jan 2000; anything after that is real."""
    return value is not None and value.year > 2000


# ── Records ────────────────────────────────────────────────────────────────


class SyncStore:
    """The synced records, kept up to date from CloudKit zone changes."""

    def __init__(self) -> None:
        self.records: dict[str, tuple[str, dict[str, Any]]] = {}
        self.sync_token: str | None = None

    def apply(self, changes: list[dict[str, Any]]) -> int:
        """Applies CloudKit records (as returned by ``changes/zone``).

        Returns how many records changed.
        """
        changed = 0
        for rec in changes:
            name = rec.get("recordName")
            if not name:
                continue
            fields = rec.get("fields") or {}
            deleted = bool(rec.get("deleted")) or bool(
                (fields.get("deleted") or {}).get("value")
            )
            if deleted:
                if self.records.pop(name, None) is not None:
                    changed += 1
                continue
            collection = (fields.get("collection") or {}).get("value", "")
            raw = (fields.get("payload") or {}).get("value", "")
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                continue
            self.records[name] = (collection, payload)
            changed += 1
        return changed

    def to_dict(self) -> dict[str, Any]:
        return {
            "sync_token": self.sync_token,
            "records": {n: [c, p] for n, (c, p) in self.records.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SyncStore:
        store = cls()
        if data:
            store.sync_token = data.get("sync_token")
            store.records = {
                n: (v[0], v[1]) for n, v in (data.get("records") or {}).items()
            }
        return store


# ── Entities ───────────────────────────────────────────────────────────────


@dataclass
class Slot:
    time: str
    week_days: list[int]
    interval_days: int
    interval_start: datetime | None


@dataclass
class Phase:
    order: int
    dose: float
    doses: list[float]
    duration_days: int


@dataclass
class Strength:
    sid: str
    strength: float
    quarters: int
    archived: bool
    reminder_enabled: bool
    threshold_quarters: int


@dataclass
class Intake:
    scheduled: datetime | None
    confirmed_at: datetime | None
    status: int
    dose: float


@dataclass
class Medication:
    sid: str
    name: str
    type: str
    dose_amount: float | None
    dose_unit: str
    times: list[str]
    week_days: list[int]
    interval_days: int
    interval_start: datetime | None
    active: bool
    on_demand: bool
    tapering: bool
    tapering_start: datetime | None
    tapering_direction: int
    use_strengths: bool
    color: int
    slots: list[Slot] = field(default_factory=list)
    phases: list[Phase] = field(default_factory=list)
    strengths: list[Strength] = field(default_factory=list)
    intakes: list[Intake] = field(default_factory=list)
    blister_remaining: float | None = None
    blister_low: bool = False


def build(store: SyncStore, tz: tzinfo) -> dict[str, Medication]:
    """Turns the synced records into medications with their related data."""
    meds: dict[str, Medication] = {}
    for name, (collection, p) in store.records.items():
        if collection != "medication":
            continue
        sid = name.split("-", 1)[1] if "-" in name else name
        type_index = p.get("type") or 0
        meds[sid] = Medication(
            sid=sid,
            name=p.get("name") or "",
            type=MEDICATION_TYPES[type_index]
            if 0 <= type_index < len(MEDICATION_TYPES)
            else "tablet",
            dose_amount=p.get("doseAmount"),
            dose_unit=p.get("doseUnit") or "mg",
            times=list(p.get("scheduledTimes") or []),
            week_days=list(p.get("weekDays") or []),
            interval_days=p.get("intervalDays") or 1,
            interval_start=from_micros(p.get("intervalStartDate"), tz),
            active=p.get("isActive") is not False,
            on_demand=bool(p.get("isOnDemand")),
            tapering=bool(p.get("isTapering")),
            tapering_start=from_micros(p.get("taperingStartDate"), tz),
            tapering_direction=p.get("taperingDirection") or 0,
            use_strengths=bool(p.get("useStrengths")),
            color=p.get("color") or 0,
        )
    for _, (collection, p) in store.records.items():
        med = meds.get(p.get("_med") or "")
        if med is None:
            continue
        if collection == "slot":
            med.slots.append(
                Slot(
                    time=p.get("time") or "08:00",
                    week_days=list(p.get("weekDays") or []),
                    interval_days=p.get("intervalDays") or 1,
                    interval_start=from_micros(p.get("intervalStartDate"), tz),
                )
            )
        elif collection == "tapering":
            med.phases.append(
                Phase(
                    order=p.get("phaseOrder") or 0,
                    dose=float(p.get("doseValue") or 0),
                    doses=[float(x) for x in p.get("doseValues") or []],
                    duration_days=p.get("durationDays") or 0,
                )
            )
        elif collection == "strength":
            med.strengths.append(
                Strength(
                    sid=p.get("sid", ""),
                    strength=float(p.get("strength") or 0),
                    quarters=p.get("quarters") or 0,
                    archived=bool(p.get("isArchived")),
                    reminder_enabled=bool(p.get("reminderEnabled")),
                    threshold_quarters=p.get("thresholdQuarters") or 0,
                )
            )
        elif collection == "intake":
            med.intakes.append(
                Intake(
                    scheduled=from_micros(p.get("scheduledTime"), tz),
                    confirmed_at=from_micros(p.get("confirmedAt"), tz),
                    status=p.get("status") or 0,
                    dose=float(p.get("doseActuallyTaken") or 0),
                )
            )
        elif collection == "blister" and p.get("isEnabled"):
            remaining = float(p.get("remainingUnits") or 0)
            total = p.get("totalUnits") or 0
            med.blister_remaining = remaining
            med.blister_low = bool(p.get("reminderEnabled")) and total > 0 and (
                remaining / total * 100 <= (p.get("reminderThresholdPercent") or 10)
            )
    for med in meds.values():
        med.slots.sort(key=lambda s: s.time)
    return meds


# ── Schedule (mirrors the app) ─────────────────────────────────────────────


def _local_date(value: datetime | None) -> date | None:
    return value.date() if value is not None else None


def _at(day: date, hhmm: str, tz: tzinfo) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def _times_for_date(
    day: date,
    times: list[str],
    week_days: list[int],
    interval_days: int,
    interval_start: date | None,
    tapering_start: date | None,
    tz: tzinfo,
) -> list[datetime]:
    """AppDateUtils.scheduledTimesForDate."""
    if tapering_start is not None and day < tapering_start:
        return []
    if interval_days > 1 and interval_start is not None:
        diff = (day - interval_start).days
        if diff < 0 or diff % interval_days != 0:
            return []
    else:
        if interval_start is not None and day < interval_start:
            return []
        if week_days and day.isoweekday() not in week_days:
            return []
    return sorted(_at(day, t, tz) for t in times)


def _slot_applies(day: date, slot: Slot) -> bool:
    """AppDateUtils._slotAppliesOnDay."""
    if slot.interval_days > 1:
        if not _is_set(slot.interval_start):
            return False
        diff = (day - slot.interval_start.date()).days
        return diff >= 0 and diff % slot.interval_days == 0
    if _is_set(slot.interval_start) and day < slot.interval_start.date():
        return False
    return not slot.week_days or day.isoweekday() in slot.week_days


def _effective_slots(med: Medication) -> list[Slot]:
    """AppDateUtils.effectiveSlots."""
    if med.slots:
        return med.slots
    return [
        Slot(t, med.week_days, med.interval_days, med.interval_start)
        for t in med.times
    ]


def _final_target_phase(med: Medication) -> Phase | None:
    if not med.phases:
        return None
    if med.tapering_direction == DIRECTION_INCREASING:
        return max(med.phases, key=lambda p: p.dose)
    markers = [p for p in med.phases if p.duration_days == 0]
    return markers[0] if markers else None


def _dose_for_slot(phase: Phase, slot_index: int) -> float:
    if 0 <= slot_index < len(phase.doses):
        return phase.doses[slot_index]
    return phase.dose


def tapering_dose(med: Medication, day: date, slot_index: int = 0) -> float | None:
    """TaperingService.doseForDate: the dose on ``day``, None if not started
    or (decreasing, no maintenance dose) finished."""
    if not med.phases or med.tapering_start is None:
        return None
    elapsed = (day - med.tapering_start.date()).days
    if elapsed < 0:
        return None
    increasing = med.tapering_direction == DIRECTION_INCREASING
    ordered = sorted(med.phases, key=lambda p: p.dose, reverse=not increasing)
    cursor = 0
    for phase in ordered:
        if elapsed < cursor + phase.duration_days:
            return _dose_for_slot(phase, slot_index)
        cursor += phase.duration_days
    if increasing:
        return _dose_for_slot(ordered[-1], slot_index)
    target = _final_target_phase(med)
    if target is not None and target.dose > 1e-9:
        return _dose_for_slot(target, slot_index)
    return None


@dataclass
class PlannedDose:
    time: datetime
    dose: float | None
    status: str  # "taken", "skipped", "open" or "upcoming"
    confirmed_at: datetime | None = None


def planned_doses(med: Medication, day: date, now: datetime) -> list[PlannedDose]:
    """The doses of ``med`` on ``day`` with their status (HomeViewModel._slotsOnDay)."""
    if not med.active or med.on_demand:
        return []
    tz = now.tzinfo
    tapering = med.tapering
    phases_apply = tapering and _is_set(med.tapering_start)
    if tapering:
        times = _times_for_date(
            day,
            med.times,
            med.week_days,
            med.interval_days,
            _local_date(med.interval_start) if _is_set(med.interval_start) else None,
            _local_date(med.tapering_start) if _is_set(med.tapering_start) else None,
            tz,
        )
    else:
        times = sorted(
            _at(day, s.time, tz) for s in _effective_slots(med) if _slot_applies(day, s)
        )

    by_time: dict[datetime, Intake] = {}
    for intake in med.intakes:
        if intake.scheduled is not None:
            by_time[intake.scheduled.replace(second=0, microsecond=0)] = intake

    result: list[PlannedDose] = []
    for t in times:
        dose: float | None = med.dose_amount
        if phases_apply:
            key = f"{t.hour:02d}:{t.minute:02d}"
            slot_index = med.times.index(key) if key in med.times else 0
            dose = tapering_dose(med, day, slot_index)
            if dose == 0:
                continue  # this time is discontinued on that day
        intake = by_time.get(t)
        if intake is not None and intake.status == STATUS_CONFIRMED:
            status = "taken"
        elif intake is not None and intake.status == STATUS_SKIPPED:
            status = "skipped"
        elif t <= now:
            status = "open"
        else:
            status = "upcoming"
        result.append(
            PlannedDose(t, dose, status, intake.confirmed_at if intake else None)
        )
    return result


@dataclass
class MedicationState:
    """What Home Assistant shows for one medication at ``now``."""

    medication: Medication
    today: list[PlannedDose]
    next_dose: PlannedDose | None
    current_dose: float | None
    last_taken: datetime | None
    stock_amount: float | None  # in the dose unit (strengths)
    stock_units: float | None  # tablets/units (blister without strengths)
    stock_low: bool
    stock_by_strength: dict[str, float]
    supply_days: int | None

    @property
    def taken_today(self) -> int:
        return sum(1 for d in self.today if d.status == "taken")

    @property
    def open_today(self) -> int:
        return sum(1 for d in self.today if d.status == "open")


def _fmt(value: float) -> str:
    return f"{value:g}"


def dose_label(med: Medication, dose: float | None) -> str:
    """"Mestinon 60 mg", or just the name when the dose is unknown."""
    if dose is None or dose <= 0:
        return med.name
    return f"{med.name} {_fmt(dose)} {med.dose_unit}"


def medication_state(med: Medication, now: datetime, horizon_days: int = 21) -> MedicationState:
    today = planned_doses(med, now.date(), now)
    next_dose = next((d for d in today if d.status == "upcoming"), None)
    day = now.date()
    for offset in range(1, horizon_days + 1):
        if next_dose is not None:
            break
        upcoming = planned_doses(med, day + timedelta(days=offset), now)
        next_dose = upcoming[0] if upcoming else None

    if med.tapering and _is_set(med.tapering_start):
        current = tapering_dose(med, now.date())
    else:
        current = med.dose_amount

    taken = [i.confirmed_at for i in med.intakes if i.status == STATUS_CONFIRMED and i.confirmed_at]
    last_taken = max(taken) if taken else None

    amount: float | None = None
    units: float | None = None
    low = False
    by_strength: dict[str, float] = {}
    live = [s for s in med.strengths if not s.archived]
    if med.use_strengths and live:
        amount = round(sum(s.quarters / 4 * s.strength for s in live), 3)
        for s in sorted(live, key=lambda s: s.strength):
            by_strength[f"{_fmt(s.strength)} {med.dose_unit}"] = s.quarters / 4
            if s.reminder_enabled and s.quarters <= s.threshold_quarters:
                low = True
    elif med.blister_remaining is not None:
        units = med.blister_remaining
        low = med.blister_low

    return MedicationState(
        med, today, next_dose, current, last_taken, amount, units, low, by_strength,
        _supply_days(med, amount, today, now) if amount is not None else None,
    )


def _supply_days(
    med: Medication, amount: float, today: list[PlannedDose], now: datetime, limit: int = 365
) -> int | None:
    """Full days the stock lasts with the planned doses (tapering included),
    counting today's doses that are still to be taken."""
    left = amount - sum(d.dose or 0 for d in today if d.status in ("open", "upcoming"))
    if left < 0:
        return 0
    planned_any = False
    for offset in range(1, limit + 1):
        need = sum(d.dose or 0 for d in planned_doses(med, now.date() + timedelta(days=offset), now))
        planned_any = planned_any or need > 0
        if need > left + 1e-9:
            return offset - 1
        left -= need
    return limit if planned_any else None


def adherence(meds: list[Medication], now: datetime, days: int = 7) -> float | None:
    """Share of planned doses of the last ``days`` days (before today) that
    were confirmed, in percent; None when nothing was planned."""
    planned = taken = 0
    for offset in range(1, days + 1):
        day = now.date() - timedelta(days=offset)
        for med in meds:
            for dose in planned_doses(med, day, now):
                planned += 1
                taken += dose.status == "taken"
    return round(taken / planned * 100, 1) if planned else None
