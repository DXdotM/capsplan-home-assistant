"""Base entities for CapsPlan."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import logic
from .const import APP_STORE_URL, CONF_PERSON, DOMAIN, MEDICATION_TYPES, SYNC_WORD
from .coordinator import CapsPlanCoordinator


def person_of(coordinator: CapsPlanCoordinator) -> str:
    """Whose CapsPlan this is; empty for a single person."""
    return (coordinator.config_entry.options.get(CONF_PERSON) or "").strip()


class CapsPlanEntity(CoordinatorEntity[CapsPlanCoordinator]):
    """An entity of the CapsPlan account (all medications)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CapsPlanCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"CapsPlan {person_of(coordinator)}".strip(),
            manufacturer="DXdotM Coding",
            model=SYNC_WORD.get(coordinator.hass.config.language.split("-")[0], SYNC_WORD["en"]),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=APP_STORE_URL,
        )


class CapsPlanMedicationEntity(CoordinatorEntity[CapsPlanCoordinator]):
    """An entity of one medication; each medication is its own device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CapsPlanCoordinator, sid: str, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self.sid = sid
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{sid}_{key}"
        med = self.state_data.medication
        person = person_of(coordinator)
        lang = coordinator.hass.config.language.split("-")[0]
        types = MEDICATION_TYPES.get(lang, MEDICATION_TYPES["en"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{sid}")},
            name=f"{med.name} ({person})" if person else med.name,
            manufacturer="CapsPlan",
            model=types.get(med.type, med.type),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def state_data(self) -> logic.MedicationState:
        return self.coordinator.data.medications[self.sid]

    @property
    def available(self) -> bool:
        return super().available and self.sid in self.coordinator.data.medications
