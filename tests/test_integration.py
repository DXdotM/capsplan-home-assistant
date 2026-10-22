"""Config flow, setup and entities in a real Home Assistant (iCloud mocked)."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.capsplan.api import CapsPlanAuthError
from custom_components.capsplan.const import (
    CONF_USER_RECORD,
    CONF_WEB_AUTH_TOKEN,
    DOMAIN,
)

from .test_logic import MED, intake, medication, record

TZ = ZoneInfo("Europe/Berlin")
CLIENT = "custom_components.capsplan.api.CapsPlanClient"


def sample_records() -> list[dict]:
    morning = datetime(2026, 10, 19, 8, tzinfo=TZ)
    return [
        record(f"medication-{MED}", "medication", medication(scheduledTimes=["08:00", "20:00"])),
        record("strength-s1", "strength", {
            "_med": MED, "divisibility": 0, "isArchived": False, "lastReminderSentAt": None,
            "looseQuarters": 0, "packSize": 0, "quarters": 40, "reminderEnabled": True,
            "sortOrder": 0, "strength": 5.0, "thresholdQuarters": 8}),
        record("intake-1", "intake", intake(morning)),
    ]


@pytest.fixture
async def setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 19, 12, tzinfo=TZ))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="_user",
        data={CONF_WEB_AUTH_TOKEN: "token-1", CONF_USER_RECORD: "_user"},
    )
    entry.add_to_hass(hass)
    with patch(f"{CLIENT}.zone_changes", return_value=(sample_records(), "sync-1")) as changes:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, changes


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with (
        patch(f"{CLIENT}.current_user", return_value="_user"),
        patch(f"{CLIENT}.zone_changes", return_value=([], "s")),
        patch("custom_components.capsplan.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WEB_AUTH_TOKEN: " pasted-token "}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_WEB_AUTH_TOKEN: "pasted-token", CONF_USER_RECORD: "_user"}


async def test_user_flow_invalid_token(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(f"{CLIENT}.current_user", side_effect=CapsPlanAuthError("expired")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_WEB_AUTH_TOKEN: "old"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_entities(hass: HomeAssistant, setup) -> None:
    entry, _ = setup
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.ramipril_taken_today").state == "1"
    assert hass.states.get("sensor.ramipril_taken_today").attributes["planned"] == 2
    assert hass.states.get("binary_sensor.ramipril_dose_open").state == "off"
    next_dose = hass.states.get("sensor.ramipril_next_dose").state
    assert datetime.fromisoformat(next_dose) == datetime(2026, 10, 19, 20, tzinfo=TZ)
    stock = hass.states.get("sensor.ramipril_stock")
    assert stock.state == "10 × 5 mg"
    assert stock.attributes["total"] == 50
    assert "unit_of_measurement" not in stock.attributes
    assert hass.states.get("binary_sensor.ramipril_stock_low").state == "off"
    assert hass.states.get("sensor.capsplan_open_doses").state == "0"
    assert hass.states.get("sensor.capsplan_next_dose").attributes["medication"] == "Ramipril"


async def test_dose_becomes_open_without_fetch(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, changes = setup
    freezer.move_to(datetime(2026, 10, 19, 19, 58, tzinfo=TZ))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ramipril_dose_open").state == "off"
    calls = changes.call_count
    freezer.tick(timedelta(minutes=3))  # 20:01, the evening dose is due
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ramipril_dose_open").state == "on"
    assert hass.states.get("binary_sensor.capsplan_dose_open").state == "on"
    assert hass.states.get("sensor.capsplan_open_doses").state == "1"
    # The minute refresh does not ask iCloud …
    assert changes.call_count == calls
    # … the regular poll does, with the stored sync token.
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert changes.call_count > calls
    assert changes.call_args.args[0] == "sync-1"


async def test_sign_in_expired_starts_reauth(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, changes = setup
    changes.side_effect = CapsPlanAuthError("expired")
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_rotated_token_is_saved(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    entry = MockConfigEntry(domain=DOMAIN, unique_id="_user",
                            data={CONF_WEB_AUTH_TOKEN: "token-1", CONF_USER_RECORD: "_user"})
    entry.add_to_hass(hass)

    async def fake_request(self, path, body=None):
        self.web_auth_token = "token-2"
        self._on_token("token-2")
        return {"zones": [{"records": [], "syncToken": "s"}]}

    with patch(f"{CLIENT}._request", fake_request):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.data[CONF_WEB_AUTH_TOKEN] == "token-2"


async def test_new_medication_adds_device(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, changes = setup
    changes.return_value = (
        [record("medication-new", "medication", medication(name="Metformin", scheduledTimes=["16:00"]))],
        "sync-2",
    )
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.metformin_next_dose") is not None
    assert hass.states.get("sensor.ramipril_next_dose") is not None


async def test_unload_and_remove(hass: HomeAssistant, setup) -> None:
    entry, _ = setup
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await hass.config_entries.async_remove(entry.entry_id)


async def test_which_doses_are_open_and_next(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 19, 13, tzinfo=TZ))
    entry = MockConfigEntry(domain=DOMAIN, unique_id="_user",
                            data={CONF_WEB_AUTH_TOKEN: "t", CONF_USER_RECORD: "_user"})
    entry.add_to_hass(hass)
    records = [
        record(f"medication-{MED}", "medication", medication(scheduledTimes=["12:00", "20:00"])),
        record("medication-b", "medication",
               medication(name="Metformin", doseAmount=500.0, scheduledTimes=["08:00", "20:00"])),
    ]
    with patch(f"{CLIENT}.zone_changes", return_value=(records, "s")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.capsplan_open").state == "Metformin 08:00, Ramipril 12:00"
    assert hass.states.get("sensor.capsplan_up_next").state == "20:00 · Metformin 500 mg, Ramipril 5 mg"
    meds = hass.states.get("sensor.capsplan_next_dose").attributes["medications"]
    assert [m["medication"] for m in meds] == ["Metformin", "Ramipril"]

    calendar = hass.states.get("calendar.capsplan_doses")
    assert calendar.attributes["message"] == "⏰ Metformin 500 mg"  # longest open first
    result = await hass.services.async_call(
        "calendar", "get_events",
        {"entity_id": "calendar.capsplan_doses",
         "start_date_time": "2026-10-19T00:00:00+02:00",
         "end_date_time": "2026-10-20T00:00:00+02:00"},
        blocking=True, return_response=True,
    )
    summaries = [e["summary"] for e in result["calendar.capsplan_doses"]["events"]]
    assert summaries == ["⏰ Metformin 500 mg", "⏰ Ramipril 5 mg", "Metformin 500 mg", "Ramipril 5 mg"]
