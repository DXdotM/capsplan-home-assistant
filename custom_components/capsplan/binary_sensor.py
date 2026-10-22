"""Binary sensors for CapsPlan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import logic
from .coordinator import CapsPlanConfigEntry, CapsPlanCoordinator
from .entity import CapsPlanEntity, CapsPlanMedicationEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MedicationBinaryDescription(BinarySensorEntityDescription):
    value: Callable[[logic.MedicationState], bool]
    attrs: Callable[[logic.MedicationState], dict[str, Any]] | None = None
    exists: Callable[[logic.MedicationState], bool] = lambda s: True


MEDICATION_BINARY: tuple[MedicationBinaryDescription, ...] = (
    MedicationBinaryDescription(
        key="dose_open",
        translation_key="dose_open",
        value=lambda s: s.open_today > 0,
        attrs=lambda s: {
            "open": [d.time.isoformat() for d in s.today if d.status == "open"],
        },
        exists=lambda s: not s.medication.on_demand,
    ),
    MedicationBinaryDescription(
        key="stock_low",
        translation_key="stock_low",
        value=lambda s: s.stock_low,
        exists=lambda s: s.stock_amount is not None or s.stock_units is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CapsPlanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([AnyDoseOpen(coordinator)])
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new() -> None:
        new = []
        for sid, state in coordinator.data.medications.items():
            for desc in MEDICATION_BINARY:
                if (sid, desc.key) not in known and desc.exists(state):
                    known.add((sid, desc.key))
                    new.append(MedicationBinarySensor(coordinator, sid, desc))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class AnyDoseOpen(CapsPlanEntity, BinarySensorEntity):
    """On while any medication has a dose that is due and not confirmed."""

    def __init__(self, coordinator: CapsPlanCoordinator) -> None:
        super().__init__(coordinator, "any_dose_open")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.open_doses > 0


class MedicationBinarySensor(CapsPlanMedicationEntity, BinarySensorEntity):
    entity_description: MedicationBinaryDescription

    def __init__(
        self, coordinator: CapsPlanCoordinator, sid: str, desc: MedicationBinaryDescription
    ) -> None:
        super().__init__(coordinator, sid, desc.key)
        self.entity_description = desc

    @property
    def is_on(self) -> bool:
        return self.entity_description.value(self.state_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self.state_data)
