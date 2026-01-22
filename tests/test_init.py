"""Tests for the Marstek Cloud integration initialization."""

from unittest.mock import AsyncMock, patch
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.marstek_cloud.const import DOMAIN


class TestIntegrationSetup:
    """Tests for integration setup and unload."""

    async def test_setup_entry_success(self, hass: HomeAssistant, setup_integration):
        """Test successful integration setup."""
        assert (
            setup_integration.state == ConfigEntryState.LOADED
        ), "Entry should be loaded"
        assert DOMAIN in hass.data, "Domain should be in hass.data"
        assert (
            setup_integration.entry_id in hass.data[DOMAIN]
        ), "Entry ID should be in domain data"

        coordinator = hass.data[DOMAIN][setup_integration.entry_id]
        assert coordinator is not None, "Coordinator should be initialized"
        assert coordinator.data is not None, "Coordinator should have data"

    async def test_setup_entry_auth_failed(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test setup with authentication failure triggers reauth flow."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Invalid email or password")
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

            assert result is False, "Setup should fail"
            # Auth failures should trigger SETUP_ERROR state (which starts reauth flow)
            assert (
                mock_config_entry.state == ConfigEntryState.SETUP_ERROR
            ), "Entry should be in error state for reauth"

    async def test_setup_entry_connection_error(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test setup with connection error results in retry."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Network error: Connection refused")
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

            assert result is False, "Setup should fail"
            assert (
                mock_config_entry.state == ConfigEntryState.SETUP_RETRY
            ), "Entry should retry setup"

    async def test_setup_entry_api_error(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test setup with API error results in retry."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("API temporarily unavailable (HTTP 503)")
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

            assert result is False, "Setup should fail"

            assert (
                mock_config_entry.state == ConfigEntryState.SETUP_RETRY
            ), "Entry should retry setup"

    async def test_unload_entry_success(self, hass: HomeAssistant, setup_integration):
        """Test successful integration unload."""
        assert await hass.config_entries.async_unload(
            setup_integration.entry_id
        ), "Unload should succeed"

        assert (
            setup_integration.state == ConfigEntryState.NOT_LOADED
        ), "Entry should be unloaded"
        assert (
            setup_integration.entry_id not in hass.data[DOMAIN]
        ), "Entry should be removed from domain data"

    async def test_reload_entry(
        self, hass: HomeAssistant, setup_integration, mock_marstek_api
    ):
        """Test reloading the integration."""
        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            assert await hass.config_entries.async_reload(
                setup_integration.entry_id
            ), "Reload should succeed"
            await hass.async_block_till_done()

            assert (
                setup_integration.state == ConfigEntryState.LOADED
            ), "Entry should be reloaded"
            assert DOMAIN in hass.data, "Domain should still be in hass.data"

    async def test_setup_updates_config_entry_with_devices(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test that setup updates config entry with device list."""
        mock_config_entry_data = dict(mock_config_entry.data)
        if "devices" in mock_config_entry_data:
            del mock_config_entry_data["devices"]

        mock_config_entry = type(mock_config_entry)(
            version=mock_config_entry.version,
            domain=mock_config_entry.domain,
            title=mock_config_entry.title,
            data=mock_config_entry_data,
            source=mock_config_entry.source,
            entry_id=mock_config_entry.entry_id,
            unique_id=mock_config_entry.unique_id,
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert (
                "devices" in mock_config_entry.data
            ), "Devices key should be added to config entry"
            assert isinstance(
                mock_config_entry.data["devices"], list
            ), "Devices should be a list"

    async def test_coordinator_stored_in_hass_data(
        self, hass: HomeAssistant, setup_integration
    ):
        """Test that coordinator is properly stored in hass.data."""
        coordinator = hass.data[DOMAIN][setup_integration.entry_id]

        assert coordinator is not None, "Coordinator should exist"
        assert hasattr(coordinator, "api"), "Coordinator should have API"
        assert hasattr(
            coordinator, "last_latency"
        ), "Coordinator should have latency tracking"
        assert coordinator.name == "Marstek Cloud", "Coordinator name should be set"

    async def test_setup_with_scan_interval_from_options(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test that setup uses scan_interval from options if available."""
        custom_scan_interval = 120
        mock_config_entry.add_to_hass(hass)

        hass.config_entries.async_update_entry(
            mock_config_entry, options={"scan_interval": custom_scan_interval}
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
            assert (
                coordinator.update_interval.total_seconds() == custom_scan_interval
            ), "Should use options scan_interval"

    async def test_setup_with_scan_interval_from_data(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test that setup falls back to scan_interval from data."""
        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            mock_config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
            expected_interval = mock_config_entry.data.get("scan_interval", 60)
            assert (
                coordinator.update_interval.total_seconds() == expected_interval
            ), "Should use data scan_interval"

    async def test_multiple_entries(self, hass: HomeAssistant, mock_marstek_api):
        """Test multiple config entries can coexist."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry
        from .conftest import TEST_PASSWORD, TEST_SCAN_INTERVAL, TEST_CAPACITY_KWH

        entry1 = MockConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Marstek Cloud (user1@example.com)",
            data={
                "email": "user1@example.com",
                "password": TEST_PASSWORD,
                "scan_interval": TEST_SCAN_INTERVAL,
                "default_capacity_kwh": TEST_CAPACITY_KWH,
            },
            options={},
            source="user",
            entry_id="entry1",
            unique_id="user1@example.com",
        )

        entry2 = MockConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Marstek Cloud (user2@example.com)",
            data={
                "email": "user2@example.com",
                "password": TEST_PASSWORD,
                "scan_interval": TEST_SCAN_INTERVAL,
                "default_capacity_kwh": TEST_CAPACITY_KWH,
            },
            options={},
            source="user",
            entry_id="entry2",
            unique_id="user2@example.com",
        )

        with patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            entry1.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry1.entry_id)
            await hass.async_block_till_done()

            entry2.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry2.entry_id)
            await hass.async_block_till_done()

            assert entry1.entry_id in hass.data[DOMAIN], "First entry should be in data"
            assert (
                entry2.entry_id in hass.data[DOMAIN]
            ), "Second entry should be in data"
            assert len(hass.data[DOMAIN]) == 2, "Should have two coordinators"
