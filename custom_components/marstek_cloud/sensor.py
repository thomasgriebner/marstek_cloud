"""Sensor platform for Marstek Cloud integration."""

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTime,
    UnitOfEnergy,
    CURRENCY_EURO,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULT_CAPACITY_KWH
from .coordinator import MarstekCoordinator

_LOGGER = logging.getLogger(__name__)

# Main battery data sensors
SENSOR_TYPES: dict[str, dict[str, Any]] = {
    "soc": {
        "name": "State of Charge",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "charge": {
        "name": "Charge Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "discharge": {
        "name": "Discharge Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "load": {
        "name": "Load Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "pv": {
        "name": "Solar Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid": {
        "name": "Grid Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "profit": {
        "name": "Profit",
        "unit": CURRENCY_EURO,
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.TOTAL,
    },
    "version": {"name": "Firmware Version", "unit": None},
    "sn": {"name": "Serial Number", "unit": None},
    "report_time": {
        "name": "Report Time",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "unit": None,
    },
}

# Diagnostic sensors for integration health
DIAGNOSTIC_SENSORS: dict[str, dict[str, Any]] = {
    "last_update": {
        "name": "Last Update",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "unit": None,
    },
    "api_latency": {
        "name": "API Latency",
        "unit": UnitOfTime.MILLISECONDS,
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "connection_status": {"name": "Connection Status", "unit": None},
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek sensors from a config entry.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration
        async_add_entities: Callback to add entities to Home Assistant
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Validate coordinator has data
    if not coordinator.data:
        _LOGGER.warning("No devices found in coordinator data - skipping entity setup")
        return

    entities = []

    for device in coordinator.data:
        devid = device.get("devid", "unknown")

        # Validate device has valid devid
        if not devid or devid == "unknown":
            _LOGGER.warning(f"Skipping device with invalid or missing devid: {device}")
            continue

        _LOGGER.debug(f"Creating sensors for device {devid}")

        # Add main battery data sensors
        for key, meta in SENSOR_TYPES.items():
            entities.append(MarstekSensor(coordinator, device, key, meta))

        # Add diagnostic sensors
        for key, meta in DIAGNOSTIC_SENSORS.items():
            entities.append(MarstekDiagnosticSensor(coordinator, device, key, meta))

        # Add total charge per device sensor
        entities.append(
            MarstekDeviceTotalChargeSensor(
                coordinator,
                device,
                "total_charge",
                {
                    "name": "Total Charge",
                    "unit": UnitOfEnergy.KILO_WATT_HOUR,
                    "device_class": SensorDeviceClass.ENERGY,
                    "state_class": SensorStateClass.TOTAL,
                },
            )
        )

        # Add calculated charge power sensor
        entities.append(
            MarstekCalculatedChargePowerSensor(
                coordinator,
                device,
                "calculated_charge_power",
                {
                    "name": "Calculated Charge Power",
                    "unit": UnitOfPower.WATT,
                    "device_class": SensorDeviceClass.POWER,
                    "state_class": SensorStateClass.MEASUREMENT,
                },
            )
        )

        # Add calculated discharge power sensor
        entities.append(
            MarstekCalculatedDischargePowerSensor(
                coordinator,
                device,
                "calculated_discharge_power",
                {
                    "name": "Calculated Discharge Power",
                    "unit": UnitOfPower.WATT,
                    "device_class": SensorDeviceClass.POWER,
                    "state_class": SensorStateClass.MEASUREMENT,
                },
            )
        )

    # Add global sensors (not device-specific)
    entities.append(MarstekTotalChargeSensor(coordinator, entry.entry_id))
    entities.append(MarstekTotalPowerSensor(coordinator, entry.entry_id))

    # Add entities - Home Assistant handles deduplication via unique_id automatically
    _LOGGER.info(
        f"Adding {len(entities)} sensor entities for {len(coordinator.data)} device(s)"
    )
    async_add_entities(entities)


class MarstekBaseSensor(CoordinatorEntity[MarstekCoordinator], SensorEntity):
    """Base class for Marstek sensors with shared device info."""

    def __init__(
        self,
        coordinator: MarstekCoordinator,
        device: dict[str, Any],
        key: str,
        meta: dict[str, Any],
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            device: Device data dictionary
            key: Sensor key (e.g., "soc", "charge")
            meta: Sensor metadata (name, unit, device_class, etc.)
        """
        super().__init__(coordinator)
        self.devid = device.get("devid", "unknown")
        self.device_data = device
        self.key = key
        self._attr_name = f"{device['name']} {meta['name']}"
        self._attr_unique_id = f"{self.devid}_{self.key}"
        self._attr_native_unit_of_measurement = meta.get("unit")

        # Set device_class and state_class if provided in metadata
        if "device_class" in meta:
            self._attr_device_class = meta["device_class"]
        if "state_class" in meta:
            self._attr_state_class = meta["state_class"]

    def _get_device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator.

        Returns:
            Device data dictionary or None if not found
        """
        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                return dev
        return None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return metadata for the device registry.

        Returns:
            Device info dictionary for Home Assistant device registry
        """
        return {
            "identifiers": {(DOMAIN, self.devid)},
            "name": self.device_data.get("name", f"Marstek {self.devid}"),
            "manufacturer": "Marstek",
            "model": self.device_data.get("type", "Unknown"),
            "sw_version": str(self.device_data.get("version", "Unknown")),
            "serial_number": self.device_data.get("sn", ""),
        }


class MarstekSensor(MarstekBaseSensor):
    """Sensor for actual battery data."""

    @property
    def native_value(self) -> Any:
        """Return the current value of the sensor.

        Returns:
            Sensor value (type depends on sensor type)
        """
        dev = self._get_device_data()
        if not dev:
            return None

        value = dev.get(self.key)

        # Special handling for timestamp sensors
        if self.key == "report_time" and value:
            try:
                # If Unix timestamp (int or float), convert to datetime
                if isinstance(value, (int, float)):
                    dt = datetime.fromtimestamp(value)
                    return dt_util.as_local(dt)
                # If ISO string, parse it
                elif isinstance(value, str):
                    return dt_util.parse_datetime(value)
            except (ValueError, OSError, TypeError):
                _LOGGER.warning(
                    "Could not parse timestamp for device %s: %s", self.devid, value
                )
                return None

        return value


class MarstekDiagnosticSensor(MarstekBaseSensor):
    """Sensor for integration diagnostics."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return the diagnostic value.

        Returns:
            Diagnostic sensor value (type depends on sensor type)
        """
        if self.key == "last_update":
            if self.coordinator.last_update_success:
                return dt_util.now()
            return None

        if self.key == "api_latency":
            return getattr(self.coordinator, "last_latency", None)

        if self.key == "connection_status":
            return "online" if self.coordinator.last_update_success else "offline"

        return None


class MarstekTotalChargeSensor(CoordinatorEntity[MarstekCoordinator], SensorEntity):
    """Sensor to calculate the total charge across all devices."""

    def __init__(self, coordinator: MarstekCoordinator, entry_id: str) -> None:
        """Initialize the total charge sensor.

        Args:
            coordinator: Data coordinator
            entry_id: Config entry ID for unique entity ID
        """
        super().__init__(coordinator)
        self._attr_name = "Total Charge Across Devices"
        self._attr_unique_id = f"total_charge_all_devices_{entry_id}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float:
        """Return the total charge across all devices.

        Returns:
            Total charge in kWh
        """
        total_charge = 0.0
        for device in self.coordinator.data:
            soc = device.get("soc", 0)
            capacity_kwh = device.get("capacity_kwh", DEFAULT_CAPACITY_KWH)
            total_charge += (soc / 100) * capacity_kwh
        return round(total_charge, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Returns:
            Dictionary with device count
        """
        return {
            "device_count": len(self.coordinator.data),
        }


class MarstekTotalPowerSensor(CoordinatorEntity[MarstekCoordinator], SensorEntity):
    """Sensor to calculate the total charge and discharge power across all devices."""

    def __init__(self, coordinator: MarstekCoordinator, entry_id: str) -> None:
        """Initialize the total power sensor.

        Args:
            coordinator: Data coordinator
            entry_id: Config entry ID for unique entity ID
        """
        super().__init__(coordinator)
        self._attr_name = "Total Power Across Devices"
        self._attr_unique_id = f"total_power_all_devices_{entry_id}"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        """Return the total power (charge - discharge) across all devices.

        Returns:
            Total power in watts
        """
        total_power = 0.0
        for device in self.coordinator.data:
            charge_power = device.get("charge", 0)
            discharge_power = device.get("discharge", 0)
            total_power += charge_power - discharge_power
        return round(total_power, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Returns:
            Dictionary with device count
        """
        return {
            "device_count": len(self.coordinator.data),
        }


class MarstekDeviceTotalChargeSensor(MarstekBaseSensor):
    """Sensor to calculate the total charge for a specific device."""

    @property
    def native_value(self) -> float | None:
        """Return the total charge for the device.

        Returns:
            Total charge in kWh or None if device not found
        """
        dev = self._get_device_data()
        if not dev:
            return None

        soc = dev.get("soc", 0)
        capacity_kwh = dev.get("capacity_kwh", DEFAULT_CAPACITY_KWH)
        return round((soc / 100) * capacity_kwh, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Returns:
            Dictionary with device name and capacity
        """
        return {
            "device_name": self.device_data.get("name"),
            "capacity_kwh": self.device_data.get("capacity_kwh", DEFAULT_CAPACITY_KWH),
        }


class MarstekCalculatedChargePowerSensor(MarstekBaseSensor):
    """Sensor to calculate charge power from PV and discharge values."""

    @property
    def native_value(self) -> float:
        """Calculate charge power as pv - discharge (only positive values).

        Returns:
            Calculated charge power in watts (0 or positive)
        """
        dev = self._get_device_data()
        if not dev:
            return 0.0

        pv = dev.get("pv", 0)
        discharge = dev.get("discharge", 0)

        # Calculate charge power: pv - discharge
        calculated_charge = pv - discharge

        # Only return positive values (charging), 0 when discharging
        return max(0.0, round(calculated_charge, 1))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary with calculation details
        """
        attrs: dict[str, Any] = {
            "calculation_method": "pv_minus_discharge",
        }

        dev = self._get_device_data()
        if dev:
            attrs.update(
                {
                    "pv_power": dev.get("pv", 0),
                    "discharge_power": dev.get("discharge", 0),
                    "raw_calculation": dev.get("pv", 0) - dev.get("discharge", 0),
                }
            )

        return attrs


class MarstekCalculatedDischargePowerSensor(MarstekBaseSensor):
    """Sensor to calculate discharge power when PV is insufficient."""

    @property
    def native_value(self) -> float:
        """Calculate discharge power as discharge - pv (only positive values).

        Returns:
            Calculated discharge power in watts (0 or positive)
        """
        dev = self._get_device_data()
        if not dev:
            return 0.0

        pv = dev.get("pv", 0)
        discharge = dev.get("discharge", 0)

        # Calculate discharge power: discharge - pv
        calculated_discharge = discharge - pv

        # Only return positive values (discharging), 0 when charging
        return max(0.0, round(calculated_discharge, 1))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dictionary with calculation details
        """
        attrs: dict[str, Any] = {
            "calculation_method": "discharge_minus_pv",
        }

        dev = self._get_device_data()
        if dev:
            attrs.update(
                {
                    "pv_power": dev.get("pv", 0),
                    "discharge_power": dev.get("discharge", 0),
                    "raw_calculation": dev.get("discharge", 0) - dev.get("pv", 0),
                }
            )

        return attrs
