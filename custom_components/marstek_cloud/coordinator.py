"""Marstek Cloud API client and data update coordinator."""

import hashlib
import aiohttp
import asyncio
import time
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_LOGIN,
    API_DEVICES,
    API_TIMEOUT,
    API_RETRY_TIMEOUT,
    IGNORED_DEVICE_TYPES,
    TOKEN_INVALID_CODES,
)

_LOGGER = logging.getLogger(__name__)


class MarstekAPI:
    """Client for communicating with Marstek Cloud API."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str
    ) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp client session for making requests
            email: User email for authentication
            password: User password for authentication
        """
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None

    async def _get_token(self) -> None:
        """Obtain new API token from Marstek Cloud.

        Raises:
            UpdateFailed: If token cannot be obtained due to auth, network, or API errors
        """
        md5_pwd = hashlib.md5(self._password.encode()).hexdigest()
        params = {"pwd": md5_pwd, "mailbox": self._email}

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.post(API_LOGIN, params=params) as resp:
                    # Check HTTP status code
                    if resp.status == 401:
                        _LOGGER.error(
                            "Marstek login failed: Invalid credentials (HTTP 401)"
                        )
                        raise UpdateFailed("Invalid email or password")
                    elif resp.status >= 500:
                        _LOGGER.warning(
                            f"Marstek API temporarily unavailable (HTTP {resp.status}) - will retry"
                        )
                        raise UpdateFailed(
                            f"API temporarily unavailable (HTTP {resp.status})"
                        )
                    elif resp.status != 200:
                        _LOGGER.warning(
                            f"Marstek login returned unexpected status HTTP {resp.status}"
                        )
                        raise UpdateFailed(f"API request failed (HTTP {resp.status})")

                    # Parse JSON response
                    try:
                        data = await resp.json()
                    except (ValueError, aiohttp.ContentTypeError) as e:
                        _LOGGER.warning(f"Marstek API returned invalid JSON: {e}")
                        raise UpdateFailed("API returned invalid response format")

                    # Validate response structure
                    if not isinstance(data, dict):
                        _LOGGER.warning(
                            f"Expected dict response, got {type(data).__name__}"
                        )
                        raise UpdateFailed(
                            f"Unexpected API response type: {type(data).__name__}"
                        )

                    # Extract token
                    token = data.get("token")
                    if not token:
                        error_msg = data.get("msg") or data.get(
                            "message", "Unknown error"
                        )
                        _LOGGER.error(f"Token request failed: {error_msg}")
                        raise UpdateFailed(f"Login failed: {error_msg}")

                    self._token = token
                    _LOGGER.info("Marstek: Obtained new API token")

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Marstek login request timed out after %d seconds - will retry",
                API_TIMEOUT,
            )
            raise UpdateFailed("API request timeout - check network connection")
        except aiohttp.ClientError as e:
            _LOGGER.warning(f"Network error during Marstek login: {e} - will retry")
            raise UpdateFailed(f"Network error: {e}")
        except UpdateFailed:
            # Re-raise UpdateFailed exceptions (already logged above)
            raise
        except Exception as e:
            # Catch any unexpected errors (these are truly unexpected)
            _LOGGER.error(f"Unexpected error during Marstek login: {e}", exc_info=True)
            raise UpdateFailed(f"Unexpected error: {e}")

    async def _parse_json_response(
        self, resp: aiohttp.ClientResponse
    ) -> dict[str, Any]:
        """Parse and validate JSON response from API.

        Args:
            resp: aiohttp response object

        Returns:
            Parsed JSON data as dictionary

        Raises:
            UpdateFailed: If response is invalid or cannot be parsed
        """
        try:
            data = await resp.json()
        except (ValueError, aiohttp.ContentTypeError) as e:
            _LOGGER.warning("Marstek API returned invalid JSON: %s", e)
            raise UpdateFailed("API returned invalid response format") from e

        if not isinstance(data, dict):
            _LOGGER.warning("Expected dict response, got %s", type(data).__name__)
            raise UpdateFailed(f"Unexpected API response type: {type(data).__name__}")

        return data

    async def _fetch_devices_with_token(self, token: str) -> dict[str, Any]:
        """Fetch devices from API with given token.

        Args:
            token: API authentication token

        Returns:
            API response data as dictionary

        Raises:
            UpdateFailed: If API request fails
        """
        params = {"token": token}

        async with self._session.get(API_DEVICES, params=params) as resp:
            # Check HTTP status code
            if resp.status >= 500:
                _LOGGER.warning(
                    "Marstek API temporarily unavailable (HTTP %d) - will retry",
                    resp.status,
                )
                raise UpdateFailed(f"API temporarily unavailable (HTTP {resp.status})")
            elif resp.status != 200:
                _LOGGER.warning("Marstek API returned HTTP %d", resp.status)

            return await self._parse_json_response(resp)

    async def _handle_token_refresh_and_retry(self) -> dict[str, Any]:
        """Refresh token and retry device fetch.

        Returns:
            API response data after token refresh

        Raises:
            UpdateFailed: If token refresh or retry fails
        """
        _LOGGER.warning("Marstek: Token expired or invalid, refreshing...")
        await self._get_token()

        try:
            async with asyncio.timeout(API_RETRY_TIMEOUT):
                return await self._fetch_devices_with_token(self._token)
        except aiohttp.ClientError as e:
            _LOGGER.warning("Network error during retry: %s", e)
            raise UpdateFailed(f"Network error on retry: {e}") from e

    def _filter_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out ignored device types.

        Args:
            devices: List of all devices from API

        Returns:
            Filtered list of devices
        """
        filtered_devices = [
            device
            for device in devices
            if device.get("type") not in IGNORED_DEVICE_TYPES
        ]

        filtered_count = len(devices) - len(filtered_devices)
        if filtered_count > 0:
            _LOGGER.debug(
                "Filtered out %d device(s) with ignored types %s",
                filtered_count,
                IGNORED_DEVICE_TYPES,
            )

        return filtered_devices

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch device list from Marstek Cloud API.

        Automatically handles token refresh if token is expired or invalid.

        Returns:
            List of device dictionaries (filtered by IGNORED_DEVICE_TYPES)

        Raises:
            UpdateFailed: If devices cannot be fetched due to auth, network, or API errors
        """
        if not self._token:
            await self._get_token()

        try:
            async with asyncio.timeout(API_TIMEOUT):
                data = await self._fetch_devices_with_token(self._token)

                _LOGGER.debug("Marstek API response: %s", data)

                # Extract response code
                code = data.get("code")

                # Handle token expiration or invalid token
                if code in TOKEN_INVALID_CODES:
                    data = await self._handle_token_refresh_and_retry()

                # Handle specific error code 8 (no access permission)
                if str(data.get("code")) == "8":
                    _LOGGER.warning(
                        "Marstek: No access permission (code 8). Token cleared, will retry on next update."
                    )
                    self._token = None
                    raise UpdateFailed(
                        "API access denied (code 8) - account may not have API permissions"
                    )

                # Check for "data" field in response
                if "data" not in data:
                    error_msg = data.get("msg") or data.get("message", "Unknown error")
                    error_code = data.get("code", "unknown")
                    _LOGGER.warning(
                        "API response missing 'data' field (code %s): %s",
                        error_code,
                        error_msg,
                    )
                    raise UpdateFailed(f"Invalid API response: {error_msg}")

                # Validate data field is a list
                if not isinstance(data["data"], list):
                    _LOGGER.warning(
                        "Expected list in 'data' field, got %s",
                        type(data["data"]).__name__,
                    )
                    raise UpdateFailed("Invalid API response structure")

                # Filter devices
                filtered_devices = self._filter_devices(data["data"])

                _LOGGER.debug(
                    "Retrieved %d device(s) from Marstek API", len(filtered_devices)
                )
                return filtered_devices

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Marstek device list request timed out after %d seconds - will retry",
                API_TIMEOUT,
            )
            raise UpdateFailed("API request timeout - check network connection")
        except aiohttp.ClientError as e:
            _LOGGER.warning("Network error while fetching devices: %s - will retry", e)
            raise UpdateFailed(f"Network error: {e}") from e
        except UpdateFailed:
            # Re-raise UpdateFailed exceptions (already logged above)
            raise
        except Exception as e:
            # Catch any unexpected errors (these are truly unexpected)
            _LOGGER.error("Unexpected error fetching devices: %s", e, exc_info=True)
            raise UpdateFailed(f"Unexpected error: {e}") from e


class MarstekCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Data coordinator for Marstek Cloud integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MarstekAPI,
        scan_interval: int,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api: Marstek API client
            scan_interval: Update interval in seconds
            config_entry: Optional config entry for this coordinator
        """
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Marstek Cloud",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )
        self.api = api
        self.last_latency: float | None = None

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API.

        Returns:
            List of device data dictionaries

        Raises:
            ConfigEntryAuthFailed: If authentication fails (invalid credentials)
            UpdateFailed: For other API errors (network, timeouts, etc.)
        """
        start = time.perf_counter()

        try:
            devices = await self.api.get_devices()
        except UpdateFailed as ex:
            error_msg = str(ex)
            # Convert auth errors to ConfigEntryAuthFailed to trigger reauth flow
            if "Invalid email or password" in error_msg or "HTTP 401" in error_msg:
                _LOGGER.error("Authentication failed: %s", error_msg)
                raise ConfigEntryAuthFailed(error_msg) from ex
            # Re-raise other UpdateFailed errors as-is
            raise

        self.last_latency = round((time.perf_counter() - start) * 1000, 1)

        # Debug: Log the processed device data
        _LOGGER.debug("Marstek processed device data: %s", devices)
        _LOGGER.debug("Marstek API latency: %s ms", self.last_latency)

        return devices
