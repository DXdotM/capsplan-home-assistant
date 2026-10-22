"""Diagnostics for CapsPlan (medication names and doses are left out)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_USER_RECORD, CONF_WEB_AUTH_TOKEN
from .coordinator import CapsPlanConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CapsPlanConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_WEB_AUTH_TOKEN, CONF_USER_RECORD}),
        "medications": len(data.medications) if data else None,
        "open_doses": data.open_doses if data else None,
        "last_sync": data.last_sync.isoformat() if data and data.last_sync else None,
        "per_medication": [
            {
                "type": s.medication.type,
                "active": s.medication.active,
                "on_demand": s.medication.on_demand,
                "tapering": s.medication.tapering,
                "slots": len(s.medication.slots),
                "phases": len(s.medication.phases),
                "intakes": len(s.medication.intakes),
                "doses_today": [d.status for d in s.today],
            }
            for s in (data.medications.values() if data else [])
        ],
    }
