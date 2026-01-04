from datetime import datetime
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTime,
    UnitOfEnergy,
    CURRENCY_EURO,
)
from .const import DOMAIN, DEFAULT_CAPACITY_KWH
import logging

# Main battery data sensors
SENSOR_TYPES = {
    "soc": {
        "name": "State of Charge",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "charge": {
        "name": "Charge Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "discharge": {
        "name": "Discharge Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "load": {
        "name": "Load Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "pv": {
        "name": "Solar Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "grid": {
        "name": "Grid Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "profit": {
        "name": "Profit",
        "unit": CURRENCY_EURO,
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": SensorStateClass.TOTAL
    },
    "version": {"name": "Firmware Version", "unit": None},
    "sn": {"name": "Serial Number", "unit": None},
    "report_time": {"name": "Report Time", "unit": UnitOfTime.SECONDS}
}

# Diagnostic sensors for integration health
DIAGNOSTIC_SENSORS = {
    "last_update": {"name": "Last Update", "unit": None},
    "api_latency": {"name": "API Latency", "unit": "ms"},
    "connection_status": {"name": "Connection Status", "unit": None},
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Marstek sensors from a config entry."""
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
        entities.append(MarstekDeviceTotalChargeSensor(coordinator, device, "total_charge", {
            "name": "Total Charge",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.MEASUREMENT
        }))

        # Add calculated charge power sensor
        entities.append(MarstekCalculatedChargePowerSensor(coordinator, device, "calculated_charge_power", {
            "name": "Calculated Charge Power",
            "unit": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT
        }))

        # Add calculated discharge power sensor
        entities.append(MarstekCalculatedDischargePowerSensor(coordinator, device, "calculated_discharge_power", {
            "name": "Calculated Discharge Power",
            "unit": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT
        }))

    # Add global sensors (not device-specific)
    entities.append(MarstekTotalChargeSensor(coordinator, entry.entry_id))
    entities.append(MarstekTotalPowerSensor(coordinator, entry.entry_id))

    # Add entities - Home Assistant handles deduplication via unique_id automatically
    if entities:
        _LOGGER.info(f"Adding {len(entities)} sensor entities for {len(coordinator.data)} device(s)")
        async_add_entities(entities)
    else:
        _LOGGER.warning("No entities created - all devices were skipped")


class MarstekBaseSensor(SensorEntity):
    """Base class for Marstek sensors with shared device info."""

    def __init__(self, coordinator, device, key, meta):
        self.coordinator = coordinator
        self.devid = device.get("devid", "unknown")
        self.device_data = device
        self.key = key
        self._attr_name = f"{device['name']} {meta['name']}"
        self._attr_unique_id = f"{self.devid}_{self.key}"  # Ensure unique ID includes device ID and sensor key
        self._attr_native_unit_of_measurement = meta["unit"]
        
        # Set device_class and state_class if provided in metadata
        if "device_class" in meta:
            self._attr_device_class = meta["device_class"]
        if "state_class" in meta:
            self._attr_state_class = meta["state_class"]

    @property
    def device_info(self):
        """Return metadata for the device registry."""
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
    def native_value(self):
        """Return the current value of the sensor."""
        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                return dev.get(self.key)
        return None

    async def async_update(self):
        """Manually trigger an update."""
        await self.coordinator.async_request_refresh()


class MarstekDiagnosticSensor(MarstekBaseSensor):
    """Sensor for integration diagnostics."""

    @property
    def native_value(self):
        """Return the diagnostic value."""
        if self.key == "last_update":
            if self.coordinator.last_update_success:
                return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return None

        elif self.key == "api_latency":
            return getattr(self.coordinator, "last_latency", None)

        elif self.key == "connection_status":
            return "online" if self.coordinator.last_update_success else "offline"

        return None


class MarstekTotalChargeSensor(SensorEntity):
    """Sensor to calculate the total charge across all devices."""

    def __init__(self, coordinator, entry_id):
        self.coordinator = coordinator
        self._attr_name = "Total Charge Across Devices"
        # Use entry_id for a stable unique ID
        self._attr_unique_id = f"total_charge_all_devices_{entry_id}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the total charge across all devices."""
        total_charge = 0
        for device in self.coordinator.data:
            soc = device.get("soc", 0)
            capacity_kwh = device.get("capacity_kwh", DEFAULT_CAPACITY_KWH)
            total_charge += (soc / 100) * capacity_kwh
        return round(total_charge, 2)

    @property
    def extra_state_attributes(self):
        return {
            "device_count": len(self.coordinator.data),
        }


class MarstekTotalPowerSensor(SensorEntity):
    """Sensor to calculate the total charge and discharge power across all devices."""

    def __init__(self, coordinator, entry_id):
        self.coordinator = coordinator
        self._attr_name = "Total Power Across Devices"
        # Use entry_id for a stable unique ID
        self._attr_unique_id = f"total_power_all_devices_{entry_id}"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the total power (charge - discharge) across all devices."""
        total_power = 0
        for device in self.coordinator.data:
            charge_power = device.get("charge", 0)
            discharge_power = device.get("discharge", 0)
            total_power += charge_power - discharge_power
        return round(total_power, 2)

    @property
    def extra_state_attributes(self):
        return {
            "device_count": len(self.coordinator.data),
        }


class MarstekDeviceTotalChargeSensor(MarstekBaseSensor):
    """Sensor to calculate the total charge for a specific device."""

    @property
    def native_value(self):
        """Return the total charge for the device."""
        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                soc = dev.get("soc", 0)
                capacity_kwh = dev.get("capacity_kwh", DEFAULT_CAPACITY_KWH)
                return round((soc / 100) * capacity_kwh, 2)
        return None

    @property
    def extra_state_attributes(self):
        return {
            "device_name": self.device_data.get("name"),
            "capacity_kwh": self.device_data.get("capacity_kwh", DEFAULT_CAPACITY_KWH),
        }


class MarstekCalculatedChargePowerSensor(MarstekBaseSensor):
    """Sensor to calculate charge power from PV and discharge values."""
    
    @property
    def native_value(self):
        """Calculate charge power as pv - discharge (only positive values)."""
        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                pv = dev.get("pv", 0)
                discharge = dev.get("discharge", 0)

                # Calculate charge power: pv - discharge
                calculated_charge = pv - discharge

                # Only return positive values (charging), 0 when discharging
                return max(0, round(calculated_charge, 1))

        return 0
        
    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {
            "calculation_method": "pv_minus_discharge",
        }

        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                attrs.update({
                    "pv_power": dev.get("pv", 0),
                    "discharge_power": dev.get("discharge", 0),
                    "raw_calculation": dev.get("pv", 0) - dev.get("discharge", 0)
                })
                break

        return attrs


class MarstekCalculatedDischargePowerSensor(MarstekBaseSensor):
    """Sensor to calculate discharge power when PV is insufficient."""
    
    @property
    def native_value(self):
        """Calculate discharge power as discharge - pv (only positive values)."""
        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                pv = dev.get("pv", 0)
                discharge = dev.get("discharge", 0)

                # Calculate discharge power: discharge - pv
                calculated_discharge = discharge - pv

                # Only return positive values (discharging), 0 when charging
                return max(0, round(calculated_discharge, 1))

        return 0
        
    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attrs = {
            "calculation_method": "discharge_minus_pv",
        }

        for dev in self.coordinator.data:
            if dev.get("devid") == self.devid:
                attrs.update({
                    "pv_power": dev.get("pv", 0),
                    "discharge_power": dev.get("discharge", 0),
                    "raw_calculation": dev.get("discharge", 0) - dev.get("pv", 0)
                })
                break

        return attrs
