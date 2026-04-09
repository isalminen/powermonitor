from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PowerMonitorCoordinator

# Unitless sensor descriptions use key-based value dispatch below.
# HA doesn't have a built-in device class for raw light counts, so
# threshold and maxlight are declared as generic measurement sensors.

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="energy",
        name="Energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key="threshold",
        name="Light Threshold",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="counts",
        icon="mdi:compare",
    ),
    SensorEntityDescription(
        key="maxlight",
        name="Peak Light Level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="counts",
        icon="mdi:brightness-7",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        PowerMonitorSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PowerMonitorSensor(CoordinatorEntity[PowerMonitorCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PowerMonitorCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name="Power Monitor",
            manufacturer="DIY",
            model="Arduino Nano 33 BLE Sense",
        )

    @property
    def available(self) -> bool:
        return (
            self.coordinator.data is not None
            and self.coordinator.data.available
        )

    @property
    def native_value(self) -> float | int | None:
        data = self.coordinator.data
        if data is None:
            return None
        match self.entity_description.key:
            case "power":
                return round(data.power_w, 1)
            case "energy":
                return data.energy_wh
            case "threshold":
                return data.threshold
            case "maxlight":
                return data.maxlight
        return None
