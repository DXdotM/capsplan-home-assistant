"""Base entities for CapsPlan."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import logic
from .const import APP_STORE_URL, DOMAIN
from .coordinator import CapsPlanCoordinator


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
            name="CapsPlan",
            manufacturer="DXdotM Coding",
            model="iCloud sync",
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{sid}")},
            name=med.name,
            manufacturer="CapsPlan",
            model=med.type.capitalize(),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def state_data(self) -> logic.MedicationState:
        return self.coordinator.data.medications[self.sid]

    @property
    def available(self) -> bool:
        return super().available and self.sid in self.coordinator.data.medications
