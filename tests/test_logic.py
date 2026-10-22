"""Tests for the CapsPlan data model and schedule logic.

The payloads are exactly what the CapsPlan app writes to iCloud.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "capsplan"))

import logic  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
MED = "e69e5ba56e7f3f8a5fb5947bc6b066a5"
STRENGTH = "bcfbdc440a53afc5aaa7091f4b07b3ba"


def micros(dt: datetime) -> int:
    return int((dt - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1_000_000)


UNSET = micros(datetime(2000, 1, 1, tzinfo=TZ))


def record(name: str, collection: str, payload: dict) -> dict:
    return {
        "recordName": name,
        "recordType": "CapsPlanEntity",
        "fields": {
            "collection": {"value": collection},
            "payload": {"value": json.dumps(payload)},
            "deleted": {"value": 0},
        },
    }


def medication(**overrides) -> dict:
    payload = {
        "activeIngredient": None, "color": 4282219118, "createdAt": UNSET,
        "doseAmount": 5.0, "doseDrops": None, "doseLiquidMl": None, "doseTablet": None,
        "doseUnit": "mg", "iconIndex": 0, "intervalDays": 1, "intervalStartDate": UNSET,
        "isActive": True, "isOnDemand": False, "isTapering": False, "maxPerDay": 0,
        "mgPerTablet": None, "minIntervalMinutes": 0, "name": "Ramipril", "notes": None,
        "scheduledTimes": ["08:00", "20:00"], "splitConfirmMode": 0, "splitPriority": [],
        "taperingCompletedAt": None, "taperingDirection": 0, "taperingIntervalDays": 1,
        "taperingStartDate": UNSET, "taperingStepDown": 0.0, "timesPerDay": 2, "type": 0,
        "useStrengths": True, "weekDays": [],
    }
    payload.update(overrides)
    return payload


def intake(at: datetime, status: int = 1) -> dict:
    return {
        "_med": MED, "confirmedAt": micros(at + timedelta(minutes=5)) if status == 1 else None,
        "doseActuallyTaken": 5.0, "editedAt": None,
        "portions": [{"_strength": STRENGTH, "fromLoose": 0, "quarters": 4, "restLoose": 0, "strength": 5.0}],
        "scheduledTime": micros(at), "snoozeCount": 0, "snoozeUntil": None, "status": status,
    }


def store_with(*records: dict) -> logic.SyncStore:
    store = logic.SyncStore()
    store.apply(list(records))
    return store


def test_sample_payloads_parse():
    store = store_with(
        record(f"medication-{MED}", "medication", medication()),
        record(f"strength-{STRENGTH}", "strength", {
            "_med": MED, "divisibility": 0, "isArchived": False, "lastReminderSentAt": None,
            "looseQuarters": 0, "packSize": 0, "quarters": 40, "reminderEnabled": True,
            "sortOrder": 0, "strength": 5.0, "thresholdQuarters": 44}),
    )
    meds = logic.build(store, TZ)
    med = meds[MED]
    assert med.name == "Ramipril"
    assert med.type == "tablet"
    assert med.interval_start.year == 2000
    state = logic.medication_state(med, datetime(2026, 10, 19, 12, tzinfo=TZ))
    assert state.stock_amount == 50  # 10 tablets of 5 mg
    assert state.stock_by_strength == {"5 mg": 10}
    assert state.stock_low  # 40 quarters ≤ threshold 44


def test_today_taken_open_upcoming():
    morning = datetime(2026, 10, 19, 8, tzinfo=TZ)
    store = store_with(
        record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00", "13:00", "20:00"])),
        record("intake-a", "intake", intake(morning)),
    )
    med = logic.build(store, TZ)[MED]
    state = logic.medication_state(med, datetime(2026, 10, 19, 14, tzinfo=TZ))
    assert [d.status for d in state.today] == ["taken", "open", "upcoming"]
    assert state.taken_today == 1 and state.open_today == 1
    assert state.next_dose.time == datetime(2026, 10, 19, 20, tzinfo=TZ)
    assert state.last_taken == morning + timedelta(minutes=5)


def test_next_dose_rolls_over_to_tomorrow():
    store = store_with(record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00"])))
    med = logic.build(store, TZ)[MED]
    state = logic.medication_state(med, datetime(2026, 10, 19, 21, tzinfo=TZ))
    assert state.next_dose.time == datetime(2026, 10, 20, 8, tzinfo=TZ)


def test_weekdays_and_interval():
    monday_only = store_with(record(f"medication-{MED}", "medication", medication(weekDays=[1], scheduledTimes=["08:00"])))
    med = logic.build(monday_only, TZ)[MED]
    tuesday = datetime(2026, 10, 20, 7, tzinfo=TZ)
    assert logic.planned_doses(med, tuesday.date(), tuesday) == []
    state = logic.medication_state(med, tuesday)
    assert state.next_dose.time.date().isoweekday() == 1

    start = micros(datetime(2026, 10, 1, tzinfo=TZ))
    every_third = store_with(record(f"medication-{MED}", "medication",
                                    medication(intervalDays=3, intervalStartDate=start, scheduledTimes=["09:00"])))
    med = logic.build(every_third, TZ)[MED]
    days = [d for d in range(1, 11) if logic.planned_doses(med, datetime(2026, 10, d).date(), tuesday)]
    assert days == [1, 4, 7, 10]


def test_saved_slots_override_times():
    store = store_with(
        record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00"])),
        record("slot-1", "slot", {"_med": MED, "intervalDays": 1, "intervalStartDate": UNSET,
                                  "slotOrder": 0, "time": "07:30", "weekDays": []}),
        record("slot-2", "slot", {"_med": MED, "intervalDays": 1, "intervalStartDate": UNSET,
                                  "slotOrder": 1, "time": "22:00", "weekDays": [6, 7]}),
    )
    med = logic.build(store, TZ)[MED]
    now = datetime(2026, 10, 24, 6, tzinfo=TZ)  # Saturday
    assert [d.time.strftime("%H:%M") for d in logic.planned_doses(med, now.date(), now)] == ["07:30", "22:00"]
    monday = datetime(2026, 10, 19, 6, tzinfo=TZ)
    assert [d.time.strftime("%H:%M") for d in logic.planned_doses(med, monday.date(), monday)] == ["07:30"]


def tapering_store(phases: list[tuple[float, int]], direction: int = 0, times=("08:00",)) -> logic.SyncStore:
    start = micros(datetime(2026, 10, 1, tzinfo=TZ))
    recs = [record(f"medication-{MED}", "medication", medication(
        name="Prednisolon", doseAmount=30.0, isTapering=True, taperingStartDate=start,
        taperingDirection=direction, scheduledTimes=list(times)))]
    for i, (dose, days) in enumerate(phases):
        recs.append(record(f"tapering-{i}", "tapering", {
            "_med": MED, "doseValue": dose, "doseValues": [], "durationDays": days, "phaseOrder": i}))
    return store_with(*recs)


def test_tapering_dose_by_day_and_maintenance():
    # 30 → 20 after a week, then 10, then stays at 5 (marker phase).
    med = logic.build(tapering_store([(30, 7), (20, 7), (10, 7), (5, 0)]), TZ)[MED]
    def dose_on(day):
        now = datetime(2026, 10, day, 12, tzinfo=TZ)
        return logic.medication_state(med, now).current_dose
    assert dose_on(1) == 30 and dose_on(7) == 30
    assert dose_on(8) == 20 and dose_on(15) == 10
    assert dose_on(22) == 5 and dose_on(30) == 5
    before = datetime(2026, 9, 30, 12, tzinfo=TZ)
    assert logic.planned_doses(med, before.date(), before) == []


def test_tapering_to_zero_ends():
    med = logic.build(tapering_store([(10, 2), (5, 2)]), TZ)[MED]
    now = datetime(2026, 10, 10, 12, tzinfo=TZ)
    assert logic.tapering_dose(med, now.date()) is None


def test_per_slot_dose_zero_drops_that_time():
    store = tapering_store([(10, 7)], times=("08:00", "20:00"))
    name = next(n for n in store.records if n.startswith("tapering-"))
    collection, payload = store.records[name]
    payload["doseValues"] = [10.0, 0.0]
    med = logic.build(store, TZ)[MED]
    now = datetime(2026, 10, 2, 6, tzinfo=TZ)
    doses = logic.planned_doses(med, now.date(), now)
    assert [(d.time.strftime("%H:%M"), d.dose) for d in doses] == [("08:00", 10.0)]


def test_increasing_stays_at_target():
    med = logic.build(tapering_store([(5, 3), (10, 3), (15, 3)], direction=1), TZ)[MED]
    assert logic.tapering_dose(med, datetime(2026, 10, 1).date()) == 5
    assert logic.tapering_dose(med, datetime(2026, 10, 20).date()) == 15


def test_skipped_inactive_on_demand():
    morning = datetime(2026, 10, 19, 8, tzinfo=TZ)
    store = store_with(
        record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00"])),
        record("intake-a", "intake", intake(morning, status=2)),
    )
    med = logic.build(store, TZ)[MED]
    now = datetime(2026, 10, 19, 9, tzinfo=TZ)
    assert [d.status for d in logic.planned_doses(med, now.date(), now)] == ["skipped"]
    med.active = False
    assert logic.planned_doses(med, now.date(), now) == []
    med.active, med.on_demand = True, True
    assert logic.planned_doses(med, now.date(), now) == []


def test_deletions_and_persistence():
    store = store_with(record(f"medication-{MED}", "medication", medication()))
    assert store.apply([{"recordName": f"medication-{MED}", "deleted": True}]) == 1
    assert logic.build(store, TZ) == {}
    store.apply([record(f"medication-{MED}", "medication", medication())])
    store.sync_token = "abc"
    again = logic.SyncStore.from_dict(json.loads(json.dumps(store.to_dict())))
    assert again.sync_token == "abc"
    assert logic.build(again, TZ)[MED].name == "Ramipril"


def test_adherence_last_week():
    now = datetime(2026, 10, 19, 12, tzinfo=TZ)
    recs = [record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00"]))]
    for d in range(1, 8):
        if d != 3:  # one missed day
            recs.append(record(f"intake-{d}", "intake", intake(datetime(2026, 10, 19 - d, 8, tzinfo=TZ))))
    meds = logic.build(store_with(*recs), TZ)
    assert logic.adherence(list(meds.values()), now) == round(6 / 7 * 100, 1)


def test_dst_change_keeps_wall_clock_time():
    # 25 Oct 2026: clocks go back in Germany; the dose stays at 08:00 local.
    store = store_with(record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00"])))
    med = logic.build(store, TZ)[MED]
    now = datetime(2026, 10, 25, 7, tzinfo=TZ)
    assert logic.planned_doses(med, now.date(), now)[0].time.hour == 8


def test_supply_days_follow_the_taper():
    # 30 mg for 7 days, then 20 mg for 7 days, then stop; one dose a day.
    store = tapering_store([(30, 7), (20, 7)])
    store.apply([record(f"strength-{STRENGTH}", "strength", {
        "_med": MED, "divisibility": 0, "isArchived": False, "lastReminderSentAt": None,
        "looseQuarters": 0, "packSize": 0, "quarters": 4 * 60, "reminderEnabled": False,
        "sortOrder": 0, "strength": 5.0, "thresholdQuarters": 0})])
    med = logic.build(store, TZ)[MED]
    # Day 1 at 06:00: 300 mg; today's 30 mg still to take → 270 left,
    # 6 more days at 30 mg (180) → 90 left, then 4 days at 20 mg (80) → 10 left.
    state = logic.medication_state(med, datetime(2026, 10, 1, 6, tzinfo=TZ))
    assert state.stock_amount == 300
    assert state.supply_days == 10
    assert state.stock_by_strength == {"5 mg": 60}
