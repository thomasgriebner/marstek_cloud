"""Pytest configuration and shared fixtures for Marstek Cloud tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from custom_components.marstek_cloud.const import (
    DOMAIN,
)

# Test constants - centralized to avoid magic values
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password"
TEST_TOKEN = "test_token_12345"
TEST_SCAN_INTERVAL = 60
TEST_CAPACITY_KWH = 5.12

TEST_DEVICE_1 = {
    "devid": "device123",
    "name": "Test Battery 1",
    "type": "HME-5",
    "soc": 85,
    "charge": 1500,
    "discharge": 0,
    "load": 800,
    "pv": 2000,
    "grid": -700,
    "profit": 12.50,
    "version": "1.2.3",
    "sn": "SN123456789",
    "report_time": 1705843200,  # Unix timestamp
    "capacity_kwh": TEST_CAPACITY_KWH,
}

TEST_DEVICE_2 = {
    "devid": "device456",
    "name": "Test Battery 2",
    "type": "HME-5",
    "soc": 60,
    "charge": 0,
    "discharge": 1200,
    "load": 1500,
    "pv": 300,
    "grid": 1200,
    "profit": 8.75,
    "version": "1.2.4",
    "sn": "SN987654321",
    "report_time": 1705843260,
    "capacity_kwh": TEST_CAPACITY_KWH,
}

# Device with missing optional fields (edge case testing)
TEST_DEVICE_MINIMAL = {
    "devid": "device_minimal",
    "name": "Minimal Device",
    "type": "HME-5",
}

# Device that should be filtered out (ignored type)
TEST_DEVICE_IGNORED = {
    "devid": "ignored_device",
    "name": "Ignored Device",
    "type": "HME-3",  # This type is in IGNORED_DEVICE_TYPES
    "soc": 50,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing.

    Returns a MockConfigEntry with standard test credentials and settings.
    """
    return MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=f"Marstek Cloud ({TEST_EMAIL})",
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            "scan_interval": TEST_SCAN_INTERVAL,
            "default_capacity_kwh": TEST_CAPACITY_KWH,
            "devices": [TEST_DEVICE_1, TEST_DEVICE_2],
        },
        options={},
        source="user",
        entry_id="test_entry_id_12345",
        unique_id=TEST_EMAIL,
    )


@pytest.fixture
def mock_config_entry_no_devices() -> MockConfigEntry:
    """Create a mock config entry without devices (for edge case testing)."""
    return MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title=f"Marstek Cloud ({TEST_EMAIL})",
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            "scan_interval": TEST_SCAN_INTERVAL,
            "default_capacity_kwh": TEST_CAPACITY_KWH,
        },
        options={},
        source="user",
        entry_id="test_entry_no_devices",
        unique_id=TEST_EMAIL,
    )


@pytest.fixture
def mock_marstek_api():
    """Create a mock MarstekAPI instance with standard responses.

    This fixture provides a fully configured API mock that returns
    realistic device data. Individual tests can override specific
    methods as needed.
    """
    api = MagicMock()

    # Configure standard successful responses
    api.get_devices = AsyncMock(return_value=[TEST_DEVICE_1, TEST_DEVICE_2])
    api._get_token = AsyncMock(return_value=None)
    api._token = TEST_TOKEN
    api._email = TEST_EMAIL
    api._password = TEST_PASSWORD

    return api


@pytest.fixture
def mock_marstek_api_single_device():
    """Create a mock API that returns only one device."""
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[TEST_DEVICE_1])
    api._get_token = AsyncMock(return_value=None)
    api._token = TEST_TOKEN
    api._email = TEST_EMAIL
    api._password = TEST_PASSWORD
    return api


@pytest.fixture
def mock_marstek_api_no_devices():
    """Create a mock API that returns no devices."""
    api = MagicMock()
    api.get_devices = AsyncMock(return_value=[])
    api._get_token = AsyncMock(return_value=None)
    api._token = TEST_TOKEN
    api._email = TEST_EMAIL
    api._password = TEST_PASSWORD
    return api


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession for API tests.

    Returns a mock session that can be used for testing HTTP interactions
    without actually making network calls. This prevents thread leaks from
    async_get_clientsession() in Home Assistant.
    """
    session = MagicMock()
    return session


@pytest.fixture(autouse=True)
def auto_mock_aiohttp_session(mock_aiohttp_session):
    """Automatically mock async_get_clientsession in ALL tests to prevent thread leaks.

    This fixture is autouse=True, meaning it applies to all tests automatically.
    It patches async_get_clientsession in both config_flow and __init__ modules
    to prevent thread leaks from real aiohttp sessions during testing.
    """
    with patch(
        "custom_components.marstek_cloud.config_flow.async_get_clientsession",
        return_value=mock_aiohttp_session,
    ), patch(
        "custom_components.marstek_cloud.async_get_clientsession",
        return_value=mock_aiohttp_session,
    ):
        yield


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_marstek_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Marstek integration with mocked API.

    This fixture:
    1. Patches the MarstekAPI class to return our mock
    2. Adds the config entry to Home Assistant
    3. Sets up the integration
    4. Waits for all async operations to complete
    5. Returns the config entry for further testing

    Usage:
        async def test_something(hass, setup_integration):
            coordinator = hass.data[DOMAIN][setup_integration.entry_id]
            # test logic
    """
    with patch(
        "custom_components.marstek_cloud.MarstekAPI",
        return_value=mock_marstek_api,
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
async def setup_integration_no_devices(
    hass: HomeAssistant,
    mock_config_entry_no_devices: MockConfigEntry,
    mock_marstek_api_no_devices: MagicMock,
) -> MockConfigEntry:
    """Set up integration with no devices (edge case)."""
    with patch(
        "custom_components.marstek_cloud.MarstekAPI",
        return_value=mock_marstek_api_no_devices,
    ):
        mock_config_entry_no_devices.add_to_hass(hass)
        assert await hass.config_entries.async_setup(
            mock_config_entry_no_devices.entry_id
        )
        await hass.async_block_till_done()

    return mock_config_entry_no_devices


@pytest.fixture
def mock_api_response_success():
    """Helper fixture for successful API response data."""

    def _create_response(devices=None):
        if devices is None:
            devices = [TEST_DEVICE_1, TEST_DEVICE_2]
        return {
            "code": 0,
            "msg": "success",
            "data": devices,
        }

    return _create_response


@pytest.fixture
def mock_api_response_error():
    """Helper fixture for error API response data."""

    def _create_error(code, message):
        return {
            "code": code,
            "msg": message,
        }

    return _create_error


@pytest.fixture
def mock_api_response_token_expired():
    """Helper fixture for token expired response."""
    return {
        "code": -1,
        "msg": "Token expired",
    }


@pytest.fixture
def mock_api_response_auth_failed():
    """Helper fixture for authentication failed response."""
    return {
        "code": 401,
        "msg": "Invalid credentials",
    }


@pytest.fixture
def mock_api_response_no_permission():
    """Helper fixture for no permission response (code 8)."""
    return {
        "code": 8,
        "msg": "No access permission",
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


# Pytest-aiohttp configuration for event loop
pytest_plugins = "pytest_homeassistant_custom_component"
