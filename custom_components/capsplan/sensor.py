"""Sensors for CapsPlan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import logic
from .coordinator import CapsPlanConfigEntry, CapsPlanCoordinator, CapsPlanData
from .entity import CapsPlanEntity, CapsPlanMedicationEntity

PARALLEL_UPDATES = 0


def _dose_list(state: logic.MedicationState) -> list[dict[str, Any]]:
    return [
        {
            "time": d.time.isoformat(),
            "dose": d.dose,
            "status": d.status,
            "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
        }
        for d in state.today
    ]


@dataclass(frozen=True, kw_only=True)
class MedicationSensorDescription(SensorEntityDescription):
    value: Callable[[logic.MedicationState], Any]
    attrs: Callable[[logic.MedicationState], dict[str, Any]] | None = None
    exists: Callable[[logic.MedicationState], bool] = lambda s: True
    unit: Callable[[logic.MedicationState], str | None] | None = None


MEDICATION_SENSORS: tuple[MedicationSensorDescription, ...] = (
    MedicationSensorDescription(
        key="next_dose",
        translation_key="next_dose",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda s: s.next_dose.time if s.next_dose else None,
        attrs=lambda s: {
            "dose": s.next_dose.dose if s.next_dose else None,
            "unit": s.medication.dose_unit,
        },
        exists=lambda s: not s.medication.on_demand,
    ),
    MedicationSensorDescription(
        key="taken_today",
        translation_key="taken_today",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.taken_today,
        attrs=lambda s: {
            "planned": len(s.today),
            "open": s.open_today,
            "skipped": sum(1 for d in s.today if d.status == "skipped"),
            "doses": _dose_list(s),
        },
        exists=lambda s: not s.medication.on_demand,
    ),
    MedicationSensorDescription(
        key="last_taken",
        translation_key="last_taken",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda s: s.last_taken,
    ),
    MedicationSensorDescription(
        key="current_dose",
        translation_key="current_dose",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.current_dose,
        unit=lambda s: s.medication.dose_unit,
        attrs=lambda s: {"tapering": s.medication.tapering},
        exists=lambda s: not s.medication.on_demand
        and (s.current_dose is not None or s.medication.tapering),
    ),
    MedicationSensorDescription(
        key="stock",
        translation_key="stock",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.stock_amount,
        unit=lambda s: s.medication.dose_unit,
        attrs=lambda s: {"tablets_by_strength": s.stock_by_strength},
        exists=lambda s: s.stock_amount is not None,
    ),
    MedicationSensorDescription(
        key="stock_units",
        translation_key="stock_units",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.stock_units,
        exists=lambda s: s.stock_units is not None,
    ),
    MedicationSensorDescription(
        key="supply_days",
        translation_key="supply_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.supply_days,
        exists=lambda s: s.stock_amount is not None and not s.medication.on_demand,
    ),
)


@dataclass(frozen=True, kw_only=True)
class AccountSensorDescription(SensorEntityDescription):
    value: Callable[[CapsPlanData], Any]
    attrs: Callable[[CapsPlanData], dict[str, Any]] | None = None


def _next_attrs(data: CapsPlanData) -> dict[str, Any]:
    if data.next_dose is None:
        return {}
    state, dose = data.next_dose
    return {
        "medication": state.medication.name,
        "dose": dose.dose,
        "unit": state.medication.dose_unit,
        "medications": [
            {"medication": s.medication.name, "dose": d.dose, "unit": s.medication.dose_unit}
            for s, d in data.next_group
        ],
    }


def _when(data: CapsPlanData, time: datetime) -> str:
    """"16:00" today, "23.10. 05:30" on another day."""
    if time.date() == data.now.date():
        return time.strftime("%H:%M")
    return time.strftime("%d.%m. %H:%M")


def _next_text(data: CapsPlanData) -> str:
    if not data.next_group:
        return "–"
    labels = ", ".join(logic.dose_label(s.medication, d.dose) for s, d in data.next_group)
    return _clip(f"{_when(data, data.next_group[0][1].time)} · {labels}")


def _open_text(data: CapsPlanData) -> str:
    if not data.open_list:
        return "–"
    return _clip(
        ", ".join(f"{s.medication.name} {d.time.strftime('%H:%M')}" for s, d in data.open_list)
    )


def _clip(text: str) -> str:
    # States are limited to 255 characters.
    return text if len(text) <= 255 else text[:254] + "…"


def _open_attrs(data: CapsPlanData) -> dict[str, Any]:
    return {
        "doses": [
            {"medication": s.medication.name, "time": d.time.isoformat(), "dose": d.dose}
            for s, d in data.open_list
        ]
    }


ACCOUNT_SENSORS: tuple[AccountSensorDescription, ...] = (
    AccountSensorDescription(
        key="next_dose_any",
        translation_key="next_dose_any",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda d: d.next_dose[1].time if d.next_dose else None,
        attrs=_next_attrs,
    ),
    AccountSensorDescription(
        key="next_doses_text",
        translation_key="next_doses_text",
        value=_next_text,
    ),
    AccountSensorDescription(
        key="open_doses_text",
        translation_key="open_doses_text",
        value=_open_text,
    ),
    AccountSensorDescription(
        key="open_doses",
        translation_key="open_doses",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.open_doses,
        attrs=_open_attrs,
    ),
    AccountSensorDescription(
        key="adherence_7d",
        translation_key="adherence_7d",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.adherence_7d,
    ),
    AccountSensorDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.last_sync,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CapsPlanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(AccountSensor(coordinator, d) for d in ACCOUNT_SENSORS)
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new() -> None:
        new = []
        for sid, state in coordinator.data.medications.items():
            for desc in MEDICATION_SENSORS:
                if (sid, desc.key) not in known and desc.exists(state):
                    known.add((sid, desc.key))
                    new.append(MedicationSensor(coordinator, sid, desc))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class AccountSensor(CapsPlanEntity, SensorEntity):
    entity_description: AccountSensorDescription

    def __init__(self, coordinator: CapsPlanCoordinator, desc: AccountSensorDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> datetime | float | int | None:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self.coordinator.data)


class MedicationSensor(CapsPlanMedicationEntity, SensorEntity):
    entity_description: MedicationSensorDescription

    def __init__(
        self, coordinator: CapsPlanCoordinator, sid: str, desc: MedicationSensorDescription
    ) -> None:
        super().__init__(coordinator, sid, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> datetime | float | int | None:
        return self.entity_description.value(self.state_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit is not None:
            return self.entity_description.unit(self.state_data)
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs is None:
            return None
        return self.entity_description.attrs(self.state_data)
