"""Tests for Marstek sensor entities."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTime,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from custom_components.marstek_cloud.const import DOMAIN, DEFAULT_CAPACITY_KWH
from custom_components.marstek_cloud.sensor import (
    MarstekSensor,
    MarstekDiagnosticSensor,
    MarstekTotalChargeSensor,
    MarstekTotalPowerSensor,
    MarstekDeviceTotalChargeSensor,
    MarstekCalculatedChargePowerSensor,
    MarstekCalculatedDischargePowerSensor,
)
from .conftest import TEST_DEVICE_1, TEST_DEVICE_2


class TestSensorSetup:
    """Tests for sensor entity setup."""

    async def test_sensor_setup_creates_entities(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test that sensor setup creates all expected entities."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, setup_integration.entry_id
        )

        assert len(entries) > 0, "Should create sensor entities"

        entity_ids = [entry.entity_id for entry in entries]
        assert any(
            "state_of_charge" in entity_id for entity_id in entity_ids
        ), "Should create SOC sensor"
        assert any(
            "charge_power" in entity_id for entity_id in entity_ids
        ), "Should create charge sensor"
        assert any(
            "discharge_power" in entity_id for entity_id in entity_ids
        ), "Should create discharge sensor"
        assert any(
            "total_charge" in entity_id for entity_id in entity_ids
        ), "Should create total charge sensor"

    async def test_sensor_setup_with_no_devices(
        self, hass: HomeAssistant, setup_integration_no_devices
    ):
        """Test sensor setup when no devices are present."""
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, setup_integration_no_devices.entry_id
        )

        assert len(entries) == 0, "Should not create entities when no devices"

    async def test_sensor_setup_with_invalid_devid(
        self, hass: HomeAssistant, mock_marstek_api, mock_config_entry
    ):
        """Test sensor setup with devices that have invalid or missing devid."""

        device_no_devid = {
            "name": "Invalid Device",
            "type": "HME-5",
            "soc": 50,
        }

        device_unknown_devid = {
            "devid": "unknown",
            "name": "Unknown Device",
            "type": "HME-5",
        }

        mock_marstek_api.get_devices = AsyncMock(
            return_value=[device_no_devid, device_unknown_devid]
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        # Global sensors are still created even with invalid device IDs
        # Filter to only device-specific sensors
        device_specific_entities = [
            e
            for e in entries
            if "total_charge_all_devices" not in e.unique_id
            and "total_power_all_devices" not in e.unique_id
        ]

        assert (
            len(device_specific_entities) == 0
        ), "Should skip devices with invalid devid"

    async def test_sensor_setup_all_devices_skipped(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test sensor setup when all devices are skipped due to invalid devid."""
        from .conftest import TEST_SCAN_INTERVAL
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        # Create devices with invalid devids that should all be skipped
        invalid_devices = [
            {"name": "Device 1", "type": "HME-5"},  # No devid
            {"devid": "unknown", "name": "Device 2", "type": "HME-5"},  # Unknown devid
            {"devid": "", "name": "Device 3", "type": "HME-5"},  # Empty devid
        ]

        mock_marstek_api.get_devices = AsyncMock(return_value=invalid_devices)

        config_entry = MockConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Marstek Test",
            data={
                "email": "test@test.com",
                "password": "test",
                "scan_interval": TEST_SCAN_INTERVAL,
            },
            entry_id="test_all_skipped",
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Verify entities are created (only global sensors)
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )

        # Should only have 2 global sensors (total charge, total power)
        assert (
            len(entries) == 2
        ), "Should create only global sensors when all devices skipped"

    async def test_sensor_device_info(self, hass: HomeAssistant, setup_integration):
        """Test that sensor entities have proper device info."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator, device, "soc", {"name": "State of Charge", "unit": PERCENTAGE}
        )

        device_info = sensor.device_info

        assert device_info["identifiers"] == {
            (DOMAIN, device["devid"])
        }, "Should have correct identifier"
        assert device_info["name"] == device["name"], "Should have correct device name"
        assert (
            device_info["manufacturer"] == "Marstek"
        ), "Should have Marstek manufacturer"
        assert device_info["model"] == device["type"], "Should have correct model"
        assert device_info["sw_version"] == str(
            device["version"]
        ), "Should have firmware version"


class TestMarstekSensor:
    """Tests for MarstekSensor class."""

    async def test_sensor_soc_value(self, hass: HomeAssistant, setup_integration):
        """Test SOC sensor returns correct value."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator,
            device,
            "soc",
            {
                "name": "State of Charge",
                "unit": PERCENTAGE,
                "device_class": SensorDeviceClass.BATTERY,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        )

        assert sensor.native_value == device["soc"], "Should return SOC value"
        assert (
            sensor.native_unit_of_measurement == PERCENTAGE
        ), "Should have percentage unit"
        assert (
            sensor.device_class == SensorDeviceClass.BATTERY
        ), "Should have battery device class"

    async def test_sensor_charge_power(self, hass: HomeAssistant, setup_integration):
        """Test charge power sensor."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator,
            device,
            "charge",
            {
                "name": "Charge Power",
                "unit": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        )

        assert sensor.native_value == device["charge"], "Should return charge power"
        assert (
            sensor.native_unit_of_measurement == UnitOfPower.WATT
        ), "Should have watt unit"

    async def test_sensor_discharge_power(self, hass: HomeAssistant, setup_integration):
        """Test discharge power sensor."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator,
            device,
            "discharge",
            {
                "name": "Discharge Power",
                "unit": UnitOfPower.WATT,
                "device_class": SensorDeviceClass.POWER,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        )

        assert (
            sensor.native_value == device["discharge"]
        ), "Should return discharge power"

    async def test_sensor_report_time_unix_timestamp(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test report time sensor with Unix timestamp."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator,
            device,
            "report_time",
            {
                "name": "Report Time",
                "device_class": SensorDeviceClass.TIMESTAMP,
                "unit": None,
            },
        )

        result = sensor.native_value
        assert result is not None, "Should parse Unix timestamp"
        assert isinstance(result, datetime), "Should return datetime object"

    async def test_sensor_report_time_invalid(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test report time sensor with missing/invalid timestamp."""
        from custom_components.marstek_cloud.coordinator import MarstekCoordinator
        from .conftest import TEST_SCAN_INTERVAL

        device_no_timestamp = {
            "devid": "device999",
            "name": "Test Device",
            "type": "HME-5",
        }

        mock_marstek_api.get_devices = AsyncMock(return_value=[device_no_timestamp])
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()

            sensor = MarstekSensor(
                coordinator,
                device_no_timestamp,
                "report_time",
                {
                    "name": "Report Time",
                    "device_class": SensorDeviceClass.TIMESTAMP,
                    "unit": None,
                },
            )

            assert (
                sensor.native_value is None
            ), "Should return None for missing timestamp"
        finally:
            await coordinator.async_shutdown()

    async def test_sensor_report_time_iso_string(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test report time sensor with ISO timestamp string."""
        from custom_components.marstek_cloud.coordinator import MarstekCoordinator
        from .conftest import TEST_SCAN_INTERVAL

        device_iso_timestamp = {
            "devid": "device_iso",
            "name": "Test Device ISO",
            "type": "HME-5",
            "report_time": "2024-01-21T10:30:00+00:00",
        }

        mock_marstek_api.get_devices = AsyncMock(return_value=[device_iso_timestamp])
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()

            sensor = MarstekSensor(
                coordinator,
                device_iso_timestamp,
                "report_time",
                {
                    "name": "Report Time",
                    "device_class": SensorDeviceClass.TIMESTAMP,
                    "unit": None,
                },
            )

            result = sensor.native_value
            assert result is not None, "Should parse ISO timestamp"
            assert isinstance(result, datetime), "Should return datetime object"
        finally:
            await coordinator.async_shutdown()

    @pytest.mark.parametrize(
        "invalid_timestamp",
        [
            "invalid_timestamp",  # String that can't be parsed
            -999999999999999,  # Out-of-range timestamp (OSError)
            None,  # None value (TypeError from isinstance check)
        ],
    )
    async def test_sensor_report_time_invalid_format(
        self, hass: HomeAssistant, mock_marstek_api, invalid_timestamp
    ):
        """Test report time sensor with various invalid timestamp formats."""
        from custom_components.marstek_cloud.coordinator import MarstekCoordinator
        from .conftest import TEST_SCAN_INTERVAL

        device_bad_timestamp = {
            "devid": "device_bad",
            "name": "Test Device Bad",
            "type": "HME-5",
            "report_time": invalid_timestamp,
        }

        mock_marstek_api.get_devices = AsyncMock(return_value=[device_bad_timestamp])
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()

            sensor = MarstekSensor(
                coordinator,
                device_bad_timestamp,
                "report_time",
                {
                    "name": "Report Time",
                    "device_class": SensorDeviceClass.TIMESTAMP,
                    "unit": None,
                },
            )

            assert (
                sensor.native_value is None
            ), f"Should return None for invalid timestamp: {invalid_timestamp}"
        finally:
            await coordinator.async_shutdown()

    async def test_sensor_missing_device(self, hass: HomeAssistant, setup_integration):
        """Test sensor when device is missing from coordinator data."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = {**TEST_DEVICE_1, "devid": "nonexistent"}

        sensor = MarstekSensor(
            coordinator, device, "soc", {"name": "State of Charge", "unit": PERCENTAGE}
        )

        assert sensor.native_value is None, "Should return None for missing device"

    @pytest.mark.parametrize(
        ("key", "expected_unit", "device_class"),
        [
            ("soc", PERCENTAGE, SensorDeviceClass.BATTERY),
            ("charge", UnitOfPower.WATT, SensorDeviceClass.POWER),
            ("pv", UnitOfPower.WATT, SensorDeviceClass.POWER),
            ("grid", UnitOfPower.WATT, SensorDeviceClass.POWER),
            ("load", UnitOfPower.WATT, SensorDeviceClass.POWER),
        ],
    )
    async def test_sensor_units_and_device_classes(
        self, hass: HomeAssistant, setup_integration, key, expected_unit, device_class
    ):
        """Test various sensors have correct units and device classes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekSensor(
            coordinator,
            device,
            key,
            {
                "name": f"Test {key}",
                "unit": expected_unit,
                "device_class": device_class,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        )

        assert (
            sensor.native_unit_of_measurement == expected_unit
        ), f"Should have correct unit for {key}"
        assert (
            sensor.device_class == device_class
        ), f"Should have correct device class for {key}"


class TestMarstekDiagnosticSensor:
    """Tests for MarstekDiagnosticSensor class."""

    async def test_diagnostic_sensor_last_update(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test last update diagnostic sensor."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDiagnosticSensor(
            coordinator,
            device,
            "last_update",
            {
                "name": "Last Update",
                "device_class": SensorDeviceClass.TIMESTAMP,
                "unit": None,
            },
        )

        assert (
            sensor.entity_category == EntityCategory.DIAGNOSTIC
        ), "Should be diagnostic category"

        coordinator.last_update_success = True
        result = sensor.native_value
        assert result is not None, "Should return timestamp when update successful"
        assert isinstance(result, datetime), "Should be datetime object"

        coordinator.last_update_success = False
        result_failed = sensor.native_value
        assert result_failed is None, "Should return None when update failed"

    async def test_diagnostic_sensor_api_latency(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test API latency diagnostic sensor."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDiagnosticSensor(
            coordinator,
            device,
            "api_latency",
            {
                "name": "API Latency",
                "unit": UnitOfTime.MILLISECONDS,
                "device_class": SensorDeviceClass.DURATION,
                "state_class": SensorStateClass.MEASUREMENT,
            },
        )

        coordinator.last_latency = 123.4
        assert sensor.native_value == 123.4, "Should return latency value"
        assert (
            sensor.native_unit_of_measurement == UnitOfTime.MILLISECONDS
        ), "Should have ms unit"

    async def test_diagnostic_sensor_connection_status(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test connection status diagnostic sensor."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDiagnosticSensor(
            coordinator,
            device,
            "connection_status",
            {"name": "Connection Status", "unit": None},
        )

        coordinator.last_update_success = True
        assert (
            sensor.native_value == "online"
        ), "Should be online when update successful"

        coordinator.last_update_success = False
        assert sensor.native_value == "offline", "Should be offline when update failed"

    async def test_diagnostic_sensor_unknown_key(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test diagnostic sensor with unknown key."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDiagnosticSensor(
            coordinator, device, "unknown_key", {"name": "Unknown Sensor", "unit": None}
        )

        assert (
            sensor.native_value is None
        ), "Should return None for unknown diagnostic key"


class TestMarstekTotalChargeSensor:
    """Tests for MarstekTotalChargeSensor class."""

    async def test_total_charge_calculation(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test total charge across all devices calculation."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        entry_id = setup_integration.entry_id

        sensor = MarstekTotalChargeSensor(coordinator, entry_id)

        expected_total = (TEST_DEVICE_1["soc"] / 100) * DEFAULT_CAPACITY_KWH + (
            TEST_DEVICE_2["soc"] / 100
        ) * DEFAULT_CAPACITY_KWH

        assert sensor.native_value == round(
            expected_total, 2
        ), "Should calculate total charge correctly"
        assert (
            sensor.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
        ), "Should have kWh unit"
        assert (
            sensor.device_class == SensorDeviceClass.ENERGY
        ), "Should have energy device class"

    async def test_total_charge_attributes(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test total charge sensor attributes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        entry_id = setup_integration.entry_id

        sensor = MarstekTotalChargeSensor(coordinator, entry_id)

        attrs = sensor.extra_state_attributes
        assert attrs["device_count"] == 2, "Should report correct device count"

    async def test_total_charge_no_devices(
        self, hass: HomeAssistant, setup_integration_no_devices
    ):
        """Test total charge with no devices."""
        coordinator = hass.data[DOMAIN][setup_integration_no_devices.entry_id]
        entry_id = setup_integration_no_devices.entry_id

        sensor = MarstekTotalChargeSensor(coordinator, entry_id)

        assert sensor.native_value == 0, "Should return 0 when no devices"


class TestMarstekTotalPowerSensor:
    """Tests for MarstekTotalPowerSensor class."""

    async def test_total_power_calculation(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test total power across all devices calculation."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        entry_id = setup_integration.entry_id

        sensor = MarstekTotalPowerSensor(coordinator, entry_id)

        expected_total = (TEST_DEVICE_1["charge"] - TEST_DEVICE_1["discharge"]) + (
            TEST_DEVICE_2["charge"] - TEST_DEVICE_2["discharge"]
        )

        assert sensor.native_value == round(
            expected_total, 2
        ), "Should calculate total power correctly"
        assert (
            sensor.native_unit_of_measurement == UnitOfPower.WATT
        ), "Should have watt unit"

    async def test_total_power_attributes(self, hass: HomeAssistant, setup_integration):
        """Test total power sensor attributes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        entry_id = setup_integration.entry_id

        sensor = MarstekTotalPowerSensor(coordinator, entry_id)

        attrs = sensor.extra_state_attributes
        assert attrs["device_count"] == 2, "Should report correct device count"


class TestMarstekDeviceTotalChargeSensor:
    """Tests for MarstekDeviceTotalChargeSensor class."""

    async def test_device_total_charge_calculation(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test device-specific total charge calculation."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDeviceTotalChargeSensor(
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

        expected_charge = (device["soc"] / 100) * DEFAULT_CAPACITY_KWH
        assert sensor.native_value == round(
            expected_charge, 2
        ), "Should calculate device charge correctly"

    async def test_device_total_charge_attributes(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test device total charge sensor attributes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekDeviceTotalChargeSensor(
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

        attrs = sensor.extra_state_attributes
        assert attrs["device_name"] == device["name"], "Should have device name"
        assert attrs["capacity_kwh"] == DEFAULT_CAPACITY_KWH, "Should have capacity"

    async def test_device_total_charge_missing_device(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test device total charge sensor when device is missing."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = {**TEST_DEVICE_1, "devid": "nonexistent_device"}

        sensor = MarstekDeviceTotalChargeSensor(
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

        assert sensor.native_value is None, "Should return None for missing device"


class TestMarstekCalculatedChargePowerSensor:
    """Tests for MarstekCalculatedChargePowerSensor class."""

    async def test_calculated_charge_power_positive(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated charge power when charging (PV > discharge)."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekCalculatedChargePowerSensor(
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

        expected = max(0, device["pv"] - device["discharge"])
        assert sensor.native_value == round(
            expected, 1
        ), "Should calculate positive charge power"

    async def test_calculated_charge_power_zero(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated charge power when discharging (PV < discharge)."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_2

        sensor = MarstekCalculatedChargePowerSensor(
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

        assert sensor.native_value == 0, "Should return 0 when discharging"

    async def test_calculated_charge_power_attributes(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated charge power sensor attributes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekCalculatedChargePowerSensor(
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

        attrs = sensor.extra_state_attributes
        assert (
            attrs["calculation_method"] == "pv_minus_discharge"
        ), "Should document calculation method"
        assert "pv_power" in attrs, "Should include PV power in attributes"
        assert (
            "discharge_power" in attrs
        ), "Should include discharge power in attributes"

    async def test_calculated_charge_power_missing_device(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated charge power when device is missing."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = {**TEST_DEVICE_1, "devid": "nonexistent"}

        sensor = MarstekCalculatedChargePowerSensor(
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

        assert sensor.native_value == 0, "Should return 0 for missing device"


class TestMarstekCalculatedDischargePowerSensor:
    """Tests for MarstekCalculatedDischargePowerSensor class."""

    async def test_calculated_discharge_power_positive(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated discharge power when discharging (discharge > PV)."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_2

        sensor = MarstekCalculatedDischargePowerSensor(
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

        expected = max(0, device["discharge"] - device["pv"])
        assert sensor.native_value == round(
            expected, 1
        ), "Should calculate positive discharge power"

    async def test_calculated_discharge_power_zero(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated discharge power when charging (discharge < PV)."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_1

        sensor = MarstekCalculatedDischargePowerSensor(
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

        assert sensor.native_value == 0, "Should return 0 when charging"

    async def test_calculated_discharge_power_attributes(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated discharge power sensor attributes."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = TEST_DEVICE_2

        sensor = MarstekCalculatedDischargePowerSensor(
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

        attrs = sensor.extra_state_attributes
        assert (
            attrs["calculation_method"] == "discharge_minus_pv"
        ), "Should document calculation method"
        assert "pv_power" in attrs, "Should include PV power in attributes"
        assert (
            "discharge_power" in attrs
        ), "Should include discharge power in attributes"

    async def test_calculated_discharge_power_missing_device(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test calculated discharge power when device is missing."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        device = {**TEST_DEVICE_2, "devid": "nonexistent"}

        sensor = MarstekCalculatedDischargePowerSensor(
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

        assert sensor.native_value == 0, "Should return 0 for missing device"
