"""Renders the overview cards from examples/ with real entity states."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import yaml
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.capsplan.const import (
    CONF_USER_RECORD,
    CONF_WEB_AUTH_TOKEN,
    DOMAIN,
)

from .test_logic import MED, medication, record

TZ = ZoneInfo("Europe/Berlin")
EXAMPLES = Path(__file__).parents[1] / "examples"


async def _setup(hass, freezer, language):
    hass.config.language = language
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 19, 13, 40, tzinfo=TZ))
    entry = MockConfigEntry(domain=DOMAIN, unique_id="u",
                            data={CONF_WEB_AUTH_TOKEN: "t", CONF_USER_RECORD: "u"})
    entry.add_to_hass(hass)
    recs = [
        record(f"medication-{MED}", "medication",
               medication(doseAmount=500.0, name="Metformin", scheduledTimes=["05:30", "12:00", "16:00"])),
        record("medication-b", "medication",
               medication(name="Ramipril", doseAmount=5.0, scheduledTimes=["19:00"])),
    ]
    with patch("custom_components.capsplan.api.CapsPlanClient.zone_changes", return_value=(recs, "s")):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _render(hass, name: str) -> str:
    card = yaml.safe_load((EXAMPLES / name).read_text())
    assert card["type"] == "markdown"
    return Template(card["content"], hass).async_render(parse_result=False)


async def test_overview_card_en(hass, freezer):
    await _setup(hass, freezer, "en")
    text = _render(hass, "overview-card.en.yaml")
    assert "- **Metformin** 500 mg · planned 05:30 · 8 h 10 min overdue\n- **Metformin** 500 mg · planned 12:00 · 1 h 40 min overdue" in text
    assert "---" in text
    assert "- **16:00** Metformin 500 mg\n- **19:00** Ramipril 5 mg" in text


async def test_overview_card_de(hass, freezer):
    await _setup(hass, freezer, "de")
    text = _render(hass, "overview-card.de.yaml")
    assert "- **Metformin** 500 mg · geplant 05:30 · seit 8 Std. 10 Min." in text
    assert "- **16:00** Metformin 500 mg\n- **19:00** Ramipril 5 mg" in text


async def test_overview_card_two_people(hass, freezer):
    hass.config.language = "en"
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 19, 13, 40, tzinfo=TZ))
    for person, med, times in (("Anna", "Metformin", ["12:00", "18:00"]), ("Ben", "Ramipril", ["08:00", "16:00"])):
        entry = MockConfigEntry(domain=DOMAIN, unique_id=person, title=f"CapsPlan {person}",
                                data={CONF_WEB_AUTH_TOKEN: "t", CONF_USER_RECORD: person},
                                options={"person": person})
        entry.add_to_hass(hass)
        recs = [record(f"medication-{person}", "medication",
                       medication(name=med, doseAmount=5.0, scheduledTimes=times))]
        with patch("custom_components.capsplan.api.CapsPlanClient.zone_changes", return_value=(recs, "s")):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
    text = _render(hass, "overview-card.en.yaml")
    assert ("- **Ramipril** 5 mg (Ben) · planned 08:00 · 5 h 40 min overdue\n"
            "- **Metformin** 5 mg (Anna) · planned 12:00 · 1 h 40 min overdue") in text
    assert "- **16:00** Ramipril 5 mg (Ben)\n- **18:00** Metformin 5 mg (Anna)" in text
