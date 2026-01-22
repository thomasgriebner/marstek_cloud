"""Tests for the Marstek coordinator."""

import asyncio
import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.marstek_cloud.coordinator import MarstekAPI, MarstekCoordinator
from .conftest import (
    TEST_EMAIL,
    TEST_PASSWORD,
    TEST_TOKEN,
    TEST_SCAN_INTERVAL,
    TEST_DEVICE_1,
    TEST_DEVICE_2,
)


class TestMarstekAPI:
    """Tests for MarstekAPI class."""

    async def test_get_token_success(self, mock_aiohttp_session):
        """Test successful token retrieval."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"token": TEST_TOKEN})

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_context

        await api._get_token()

        assert (
            api._token == TEST_TOKEN
        ), "Token should be stored after successful retrieval"
        mock_aiohttp_session.post.assert_called_once()

    async def test_get_token_invalid_credentials(self, mock_aiohttp_session):
        """Test token retrieval with invalid credentials (HTTP 401)."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, "wrong_password")

        mock_response = MagicMock()
        mock_response.status = 401
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert (
            "invalid email or password" in error_msg
        ), "Should indicate invalid credentials"

    async def test_get_token_server_error(self, mock_aiohttp_session):
        """Test token retrieval with server error (HTTP 500+)."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 503

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert (
            "temporarily unavailable" in error_msg
        ), "Should indicate temporary unavailability"

    async def test_get_token_unexpected_status(self, mock_aiohttp_session):
        """Test token retrieval with unexpected HTTP status code."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 418

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert (
            "api request failed" in error_msg or "http 418" in error_msg
        ), "Should indicate unexpected status"

    async def test_get_token_non_dict_response(self, mock_aiohttp_session):
        """Test token retrieval with non-dict JSON response."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[1, 2, 3])

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert (
            "unexpected" in error_msg or "type" in error_msg
        ), "Should indicate unexpected response type"

    async def test_get_token_timeout(self, mock_aiohttp_session):
        """Test token retrieval with timeout."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_aiohttp_session.post.side_effect = asyncio.TimeoutError()

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg, "Should indicate timeout error"

    async def test_get_token_network_error(self, mock_aiohttp_session):
        """Test token retrieval with network error."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_aiohttp_session.post.side_effect = aiohttp.ClientError(
            "Connection refused"
        )

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert "network error" in error_msg, "Should indicate network error"

    async def test_get_token_invalid_json(self, mock_aiohttp_session):
        """Test token retrieval with invalid JSON response."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert "invalid response format" in error_msg, "Should indicate invalid JSON"

    async def test_get_token_missing_token_field(self, mock_aiohttp_session):
        """Test token retrieval when token field is missing."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"msg": "error"})
        mock_aiohttp_session.post.return_value.__aenter__.return_value = mock_response

        with pytest.raises(UpdateFailed) as exc_info:
            await api._get_token()

        error_msg = str(exc_info.value).lower()
        assert "login failed" in error_msg, "Should indicate login failure"

    async def test_get_devices_success(self, mock_aiohttp_session):
        """Test successful device retrieval."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": [TEST_DEVICE_1, TEST_DEVICE_2],
            }
        )
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

        devices = await api.get_devices()

        assert len(devices) == 2, "Should return 2 devices"
        assert (
            devices[0]["devid"] == TEST_DEVICE_1["devid"]
        ), "Should match first device"
        assert (
            devices[1]["devid"] == TEST_DEVICE_2["devid"]
        ), "Should match second device"

    async def test_get_devices_requests_token_if_missing(self, mock_aiohttp_session):
        """Test that get_devices requests token if not present."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = None

        token_response = MagicMock()
        token_response.status = 200
        token_response.json = AsyncMock(return_value={"token": TEST_TOKEN})

        devices_response = MagicMock()
        devices_response.status = 200
        devices_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": [TEST_DEVICE_1],
            }
        )

        mock_aiohttp_session.post.return_value.__aenter__.return_value = token_response
        mock_aiohttp_session.get.return_value.__aenter__.return_value = devices_response

        devices = await api.get_devices()

        assert api._token == TEST_TOKEN, "Token should be retrieved and stored"
        assert len(devices) == 1, "Should return device data"
        mock_aiohttp_session.post.assert_called_once()

    @pytest.mark.parametrize(
        ("error_code", "expected_behavior"),
        [
            (-1, "token_refresh"),
            ("-1", "token_refresh"),
            (401, "token_refresh"),
            ("401", "token_refresh"),
            (403, "token_refresh"),
            ("403", "token_refresh"),
        ],
    )
    async def test_get_devices_token_expiration_codes(
        self, mock_aiohttp_session, error_code, expected_behavior
    ):
        """Test device retrieval with various token expiration codes."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = "expired_token"

        expired_response = MagicMock()
        expired_response.status = 200
        expired_response.json = AsyncMock(
            return_value={
                "code": error_code,
                "msg": "Token expired",
            }
        )

        token_response = MagicMock()
        token_response.status = 200
        token_response.json = AsyncMock(return_value={"token": "new_token"})

        success_response = MagicMock()
        success_response.status = 200
        success_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": [TEST_DEVICE_1],
            }
        )

        mock_aiohttp_session.get.return_value.__aenter__.side_effect = [
            expired_response,
            success_response,
        ]
        mock_aiohttp_session.post.return_value.__aenter__.return_value = token_response

        devices = await api.get_devices()

        assert api._token == "new_token", "Token should be refreshed"
        assert len(devices) == 1, "Should return devices after token refresh"

    async def test_get_devices_code_8_no_permission(self, mock_aiohttp_session):
        """Test device retrieval with code 8 (no access permission)."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "code": 8,
                "msg": "No access permission",
            }
        )
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        assert api._token is None, "Token should be cleared on code 8"
        error_msg = str(exc_info.value).lower()
        assert "access denied" in error_msg, "Should indicate access denied"

    async def test_get_devices_filters_ignored_types(self, mock_aiohttp_session):
        """Test that get_devices filters out ignored device types."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        devices_with_ignored = [
            TEST_DEVICE_1,
            {"devid": "ignored", "type": "HME-3", "name": "Ignored"},
            TEST_DEVICE_2,
        ]

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": devices_with_ignored,
            }
        )
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

        devices = await api.get_devices()

        assert len(devices) == 2, "Should filter out ignored device type"
        assert all(
            d.get("type") != "HME-3" for d in devices
        ), "No HME-3 devices should be present"

    async def test_get_devices_missing_data_field(self, mock_aiohttp_session):
        """Test device retrieval when data field is missing."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "code": 99,
                "msg": "Some error",
            }
        )
        mock_aiohttp_session.get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert "invalid api response" in error_msg, "Should indicate invalid response"

    async def test_get_devices_timeout(self, mock_aiohttp_session):
        """Test device retrieval with timeout."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_aiohttp_session.get.side_effect = asyncio.TimeoutError()

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg, "Should indicate timeout"

    async def test_get_devices_network_error(self, mock_aiohttp_session):
        """Test device retrieval with network error."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_aiohttp_session.get.side_effect = aiohttp.ClientError("Connection reset")

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert "network error" in error_msg, "Should indicate network error"

    async def test_get_devices_unexpected_error(self, mock_aiohttp_session):
        """Test device retrieval with unexpected error."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_aiohttp_session.get.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert "unexpected error" in error_msg, "Should indicate unexpected error"

    async def test_get_devices_server_error(self, mock_aiohttp_session):
        """Test device retrieval with server error (HTTP 500+)."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 502

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "temporarily unavailable" in error_msg or "http 502" in error_msg
        ), "Should indicate server error"

    async def test_get_devices_unexpected_status(self, mock_aiohttp_session):
        """Test device retrieval with unexpected HTTP status code."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(return_value={"code": 0, "data": []})

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_context

        devices = await api.get_devices()
        assert devices == [], "Should handle non-200 status gracefully if JSON is valid"

    async def test_get_devices_invalid_json(self, mock_aiohttp_session):
        """Test device retrieval with invalid JSON response."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert "invalid response format" in error_msg, "Should indicate invalid JSON"

    async def test_get_devices_non_dict_response(self, mock_aiohttp_session):
        """Test device retrieval with non-dict JSON response."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value="invalid")

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "unexpected" in error_msg or "type" in error_msg
        ), "Should indicate unexpected response type"

    async def test_get_devices_data_not_list(self, mock_aiohttp_session):
        """Test device retrieval when data field is not a list."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = TEST_TOKEN

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {"not": "a list"},
            }
        )

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "invalid" in error_msg or "structure" in error_msg
        ), "Should indicate invalid data structure"

    async def test_get_devices_retry_fails(self, mock_aiohttp_session):
        """Test device retrieval when token refresh succeeds but retry fails."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = "expired_token"

        expired_response = MagicMock()
        expired_response.status = 200
        expired_response.json = AsyncMock(
            return_value={
                "code": -1,
                "msg": "Token expired",
            }
        )

        token_response = MagicMock()
        token_response.status = 200
        token_response.json = AsyncMock(return_value={"token": "new_token"})

        failed_retry_response = MagicMock()
        failed_retry_response.status = 500

        mock_get_context1 = MagicMock()
        mock_get_context1.__aenter__ = AsyncMock(return_value=expired_response)
        mock_get_context1.__aexit__ = AsyncMock(return_value=None)

        mock_get_context2 = MagicMock()
        mock_get_context2.__aenter__ = AsyncMock(return_value=failed_retry_response)
        mock_get_context2.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=token_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_get_context1
            return mock_get_context2

        mock_aiohttp_session.get.side_effect = get_side_effect
        mock_aiohttp_session.post.return_value = mock_post_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "retry failed" in error_msg or "http 500" in error_msg
        ), "Should indicate retry failure"

    async def test_get_devices_retry_invalid_json(self, mock_aiohttp_session):
        """Test device retrieval when retry returns invalid JSON."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = "expired_token"

        expired_response = MagicMock()
        expired_response.status = 200
        expired_response.json = AsyncMock(
            return_value={
                "code": 401,
                "msg": "Token expired",
            }
        )

        token_response = MagicMock()
        token_response.status = 200
        token_response.json = AsyncMock(return_value={"token": "new_token"})

        retry_response = MagicMock()
        retry_response.status = 200
        retry_response.json = AsyncMock(side_effect=ValueError("Bad JSON"))

        mock_get_context1 = MagicMock()
        mock_get_context1.__aenter__ = AsyncMock(return_value=expired_response)
        mock_get_context1.__aexit__ = AsyncMock(return_value=None)

        mock_get_context2 = MagicMock()
        mock_get_context2.__aenter__ = AsyncMock(return_value=retry_response)
        mock_get_context2.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=token_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_get_context1
            return mock_get_context2

        mock_aiohttp_session.get.side_effect = get_side_effect
        mock_aiohttp_session.post.return_value = mock_post_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "invalid" in error_msg or "retry" in error_msg
        ), "Should indicate retry JSON error"

    async def test_get_devices_retry_network_error(self, mock_aiohttp_session):
        """Test device retrieval when retry encounters network error."""
        api = MarstekAPI(mock_aiohttp_session, TEST_EMAIL, TEST_PASSWORD)
        api._token = "expired_token"

        expired_response = MagicMock()
        expired_response.status = 200
        expired_response.json = AsyncMock(
            return_value={
                "code": 403,
                "msg": "Token expired",
            }
        )

        token_response = MagicMock()
        token_response.status = 200
        token_response.json = AsyncMock(return_value={"token": "new_token"})

        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=expired_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)

        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=token_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_get_context
            raise aiohttp.ClientError("Connection refused")

        mock_aiohttp_session.get.side_effect = get_side_effect
        mock_aiohttp_session.post.return_value = mock_post_context

        with pytest.raises(UpdateFailed) as exc_info:
            await api.get_devices()

        error_msg = str(exc_info.value).lower()
        assert (
            "network error" in error_msg or "retry" in error_msg
        ), "Should indicate network error on retry"


class TestMarstekCoordinator:
    """Tests for MarstekCoordinator class."""

    async def test_coordinator_initialization(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator initialization."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        assert coordinator.api == mock_marstek_api, "API should be stored"
        assert coordinator.name == "Marstek Cloud", "Name should be set"
        assert (
            coordinator.update_interval.total_seconds() == TEST_SCAN_INTERVAL
        ), "Update interval should match"
        assert coordinator.last_latency is None, "Latency should be None initially"

    async def test_coordinator_first_refresh_success(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator first refresh with successful data fetch."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()

            assert coordinator.data is not None, "Data should be populated"
            assert len(coordinator.data) == 2, "Should have 2 devices"
            assert (
                coordinator.last_update_success is True
            ), "Update should be successful"
            assert coordinator.last_latency is not None, "Latency should be measured"
            assert coordinator.last_latency >= 0, "Latency should be non-negative"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_refresh_updates_latency(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test that coordinator refresh updates latency measurement."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()

            assert coordinator.last_latency is not None, "Latency should be measured"
            assert isinstance(
                coordinator.last_latency, (int, float)
            ), "Latency should be numeric"
            assert coordinator.last_latency >= 0, "Latency should be non-negative"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_handles_update_failed(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator handles UpdateFailed exceptions gracefully."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)
        mock_marstek_api.get_devices = AsyncMock(side_effect=UpdateFailed("API Error"))

        try:
            await coordinator.async_refresh()

            assert (
                coordinator.last_update_success is False
            ), "Update should be marked as failed"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_handles_network_errors(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator handles network errors gracefully."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)
        mock_marstek_api.get_devices = AsyncMock(
            side_effect=UpdateFailed("Network error: Connection refused")
        )

        try:
            await coordinator.async_refresh()

            assert (
                coordinator.last_update_success is False
            ), "Update should be marked as failed"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_multiple_refreshes(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator handles multiple refresh cycles correctly."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        try:
            await coordinator.async_refresh()
            first_latency = coordinator.last_latency

            await coordinator.async_refresh()
            second_latency = coordinator.last_latency

            assert first_latency is not None, "First latency should be recorded"
            assert second_latency is not None, "Second latency should be recorded"
            assert coordinator.data is not None, "Data should persist across refreshes"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_empty_device_list(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator handles empty device list correctly."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)
        mock_marstek_api.get_devices = AsyncMock(return_value=[])

        try:
            await coordinator.async_refresh()

            assert coordinator.data == [], "Data should be empty list"
            assert (
                coordinator.last_update_success is True
            ), "Empty list is valid response"
        finally:
            await coordinator.async_shutdown()

    async def test_coordinator_shutdown_cleanup(
        self, hass: HomeAssistant, mock_marstek_api
    ):
        """Test coordinator shutdown properly cleans up resources."""
        coordinator = MarstekCoordinator(hass, mock_marstek_api, TEST_SCAN_INTERVAL)

        await coordinator.async_refresh()
        await coordinator.async_shutdown()

        assert (
            coordinator._unsub_refresh is None
        ), "Refresh subscription should be cleaned up"
