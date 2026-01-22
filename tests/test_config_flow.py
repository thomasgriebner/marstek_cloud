"""Tests for the Marstek config flow."""

import pytest
from unittest.mock import AsyncMock, patch
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.marstek_cloud.config_flow import (
    InvalidAuth,
    CannotConnect,
    validate_input,
)
from custom_components.marstek_cloud.const import DOMAIN, DEFAULT_CAPACITY_KWH
from .conftest import (
    TEST_EMAIL,
    TEST_PASSWORD,
    TEST_SCAN_INTERVAL,
)


class TestValidateInput:
    """Tests for validate_input function."""

    async def test_validate_input_success(self, hass: HomeAssistant, mock_marstek_api):
        """Test successful validation of user input."""
        user_input = {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        }

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await validate_input(hass, user_input)

        assert (
            result["title"] == f"Marstek Cloud ({TEST_EMAIL})"
        ), "Title should include email"
        mock_marstek_api.get_devices.assert_called_once()

    async def test_validate_input_invalid_auth(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test validation with invalid credentials."""
        user_input = {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: "wrong_password",
        }

        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Invalid email or password")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            with pytest.raises(InvalidAuth):
                await validate_input(hass, user_input)

    async def test_validate_input_cannot_connect(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test validation when unable to connect to API."""
        user_input = {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        }

        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Network error: Connection refused")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            with pytest.raises(CannotConnect):
                await validate_input(hass, user_input)


class TestMarstekConfigFlow:
    """Tests for MarstekConfigFlow class."""

    async def test_user_flow_success(self, hass: HomeAssistant, mock_marstek_api):
        """Test successful user configuration flow."""
        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ), patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
            )

            assert result["type"] == FlowResultType.FORM, "Should show form"
            assert result["step_id"] == "user", "Should be user step"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: TEST_PASSWORD,
                    "scan_interval": TEST_SCAN_INTERVAL,
                    "default_capacity_kwh": DEFAULT_CAPACITY_KWH,
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY, "Should create entry"
            assert (
                result["title"] == f"Marstek Cloud ({TEST_EMAIL})"
            ), "Title should match"
            assert result["data"][CONF_EMAIL] == TEST_EMAIL, "Email should be stored"
            assert (
                result["data"]["scan_interval"] == TEST_SCAN_INTERVAL
            ), "Scan interval should be stored"

    async def test_user_flow_invalid_auth(self, hass: HomeAssistant, mock_marstek_api):
        """Test user flow with invalid authentication."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Invalid email or password")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: "wrong_password",
                    "scan_interval": TEST_SCAN_INTERVAL,
                    "default_capacity_kwh": DEFAULT_CAPACITY_KWH,
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert (
                result["errors"]["base"] == "invalid_auth"
            ), "Should show invalid auth error"

    async def test_user_flow_cannot_connect(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test user flow when unable to connect."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Network error: Connection refused")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: TEST_PASSWORD,
                    "scan_interval": TEST_SCAN_INTERVAL,
                    "default_capacity_kwh": DEFAULT_CAPACITY_KWH,
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert (
                result["errors"]["base"] == "cannot_connect"
            ), "Should show connection error"

    async def test_user_flow_unknown_error(self, hass: HomeAssistant, mock_marstek_api):
        """Test user flow with unexpected error."""
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: TEST_PASSWORD,
                    "scan_interval": TEST_SCAN_INTERVAL,
                    "default_capacity_kwh": DEFAULT_CAPACITY_KWH,
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert result["errors"]["base"] == "unknown", "Should show unknown error"

    async def test_reauth_flow_success(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test successful reauth flow."""
        mock_config_entry.add_to_hass(hass)

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_REAUTH,
                    "entry_id": mock_config_entry.entry_id,
                },
                data=mock_config_entry.data,
            )

            assert result["type"] == FlowResultType.FORM, "Should show form"
            assert (
                result["step_id"] == "reauth_confirm"
            ), "Should be reauth_confirm step"

            new_password = "new_password"
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: new_password,
                },
            )

            assert result["type"] == FlowResultType.ABORT, "Should abort after success"
            assert result["reason"] == "reauth_successful", "Should indicate success"

    async def test_reauth_flow_invalid_auth(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test reauth flow with invalid credentials."""
        mock_config_entry.add_to_hass(hass)
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Invalid email or password")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_REAUTH,
                    "entry_id": mock_config_entry.entry_id,
                },
                data=mock_config_entry.data,
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: "wrong_password",
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert (
                result["errors"]["base"] == "invalid_auth"
            ), "Should show invalid auth error"

    async def test_reauth_flow_cannot_connect(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test reauth flow when unable to connect."""
        mock_config_entry.add_to_hass(hass)
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Network error: Connection refused")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_REAUTH,
                    "entry_id": mock_config_entry.entry_id,
                },
                data=mock_config_entry.data,
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: TEST_PASSWORD,
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert (
                result["errors"]["base"] == "cannot_connect"
            ), "Should show connection error"

    async def test_reauth_flow_unknown_error(
        self, hass: HomeAssistant, mock_config_entry, mock_marstek_api
    ):
        """Test reauth flow with unexpected error."""
        mock_config_entry.add_to_hass(hass)
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_REAUTH,
                    "entry_id": mock_config_entry.entry_id,
                },
                data=mock_config_entry.data,
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_EMAIL: TEST_EMAIL,
                    CONF_PASSWORD: TEST_PASSWORD,
                },
            )

            assert result["type"] == FlowResultType.FORM, "Should show form again"
            assert result["errors"]["base"] == "unknown", "Should show unknown error"

    async def test_options_flow_success(self, hass: HomeAssistant, mock_config_entry):
        """Test successful options flow."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        assert result["type"] == FlowResultType.FORM, "Should show form"
        assert result["step_id"] == "init", "Should be init step"

        new_scan_interval = 120
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"scan_interval": new_scan_interval},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY, "Should create entry"
        assert (
            result["data"]["scan_interval"] == new_scan_interval
        ), "Scan interval should be updated"

    async def test_options_flow_no_devices(
        self, hass: HomeAssistant, mock_config_entry_no_devices
    ):
        """Test options flow when no devices are configured."""
        mock_config_entry_no_devices.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(
            mock_config_entry_no_devices.entry_id
        )

        assert result["type"] == FlowResultType.ABORT, "Should abort"
        assert result["reason"] == "no_devices_found", "Should indicate no devices"

    @pytest.mark.parametrize(
        ("scan_interval", "expected_valid"),
        [
            (10, True),
            (60, True),
            (3600, True),
            (5, False),
            (5000, False),
        ],
    )
    async def test_scan_interval_validation(
        self, hass: HomeAssistant, mock_marstek_api, scan_interval, expected_valid
    ):
        """Test scan interval validation."""
        with patch(
            "custom_components.marstek_cloud.config_flow.MarstekAPI",
            return_value=mock_marstek_api,
        ), patch(
            "custom_components.marstek_cloud.MarstekAPI",
            return_value=mock_marstek_api,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
            )

            try:
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={
                        CONF_EMAIL: TEST_EMAIL,
                        CONF_PASSWORD: TEST_PASSWORD,
                        "scan_interval": scan_interval,
                        "default_capacity_kwh": DEFAULT_CAPACITY_KWH,
                    },
                )

                if expected_valid:
                    assert (
                        result["type"] == FlowResultType.CREATE_ENTRY
                    ), "Valid scan interval should succeed"
                else:
                    assert (
                        result["type"] == FlowResultType.FORM
                    ), "Invalid scan interval should show form again"
            except Exception:
                assert (
                    not expected_valid
                ), "Invalid scan interval should raise exception"
