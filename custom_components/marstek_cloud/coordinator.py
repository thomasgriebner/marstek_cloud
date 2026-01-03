import hashlib
import aiohttp
import async_timeout
import asyncio
import time
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import API_LOGIN, API_DEVICES, IGNORED_DEVICE_TYPES

_LOGGER = logging.getLogger(__name__)

class MarstekAPI:
    def __init__(self, session: aiohttp.ClientSession, email: str, password: str):
        self._session = session
        self._email = email
        self._password = password
        self._token = None

    async def _get_token(self):
        """Obtain new API token from Marstek Cloud.

        Raises:
            UpdateFailed: If token cannot be obtained due to auth, network, or API errors
        """
        md5_pwd = hashlib.md5(self._password.encode()).hexdigest()
        params = {"pwd": md5_pwd, "mailbox": self._email}

        try:
            async with async_timeout.timeout(10):
                async with self._session.post(API_LOGIN, params=params) as resp:
                    # Check HTTP status code
                    if resp.status == 401:
                        _LOGGER.error("Marstek login failed: Invalid credentials (HTTP 401)")
                        raise UpdateFailed("Invalid email or password")
                    elif resp.status >= 500:
                        _LOGGER.warning(f"Marstek API temporarily unavailable (HTTP {resp.status}) - will retry")
                        raise UpdateFailed(f"API temporarily unavailable (HTTP {resp.status})")
                    elif resp.status != 200:
                        _LOGGER.warning(f"Marstek login returned unexpected status HTTP {resp.status}")
                        raise UpdateFailed(f"API request failed (HTTP {resp.status})")

                    # Parse JSON response
                    try:
                        data = await resp.json()
                    except (ValueError, aiohttp.ContentTypeError) as e:
                        _LOGGER.warning(f"Marstek API returned invalid JSON: {e}")
                        raise UpdateFailed("API returned invalid response format")

                    # Validate response structure
                    if not isinstance(data, dict):
                        _LOGGER.warning(f"Expected dict response, got {type(data).__name__}")
                        raise UpdateFailed(f"Unexpected API response type: {type(data).__name__}")

                    # Extract token
                    token = data.get("token")
                    if not token:
                        error_msg = data.get("msg") or data.get("message", "Unknown error")
                        _LOGGER.error(f"Token request failed: {error_msg}")
                        raise UpdateFailed(f"Login failed: {error_msg}")

                    self._token = token
                    _LOGGER.info("Marstek: Obtained new API token")

        except asyncio.TimeoutError:
            _LOGGER.warning("Marstek login request timed out after 10 seconds - will retry")
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

    async def get_devices(self):
        """Fetch device list from Marstek Cloud API.

        Automatically handles token refresh if token is expired or invalid.

        Returns:
            list: List of device dictionaries (filtered by IGNORED_DEVICE_TYPES)

        Raises:
            UpdateFailed: If devices cannot be fetched due to auth, network, or API errors
        """
        if not self._token:
            await self._get_token()

        params = {"token": self._token}

        try:
            async with async_timeout.timeout(10):
                async with self._session.get(API_DEVICES, params=params) as resp:
                    # Check HTTP status code
                    if resp.status >= 500:
                        _LOGGER.warning(f"Marstek API temporarily unavailable (HTTP {resp.status}) - will retry")
                        raise UpdateFailed(f"API temporarily unavailable (HTTP {resp.status})")
                    elif resp.status != 200:
                        _LOGGER.warning(f"Marstek API returned HTTP {resp.status}")

                    # Parse JSON response
                    try:
                        data = await resp.json()
                    except (ValueError, aiohttp.ContentTypeError) as e:
                        _LOGGER.warning(f"Marstek API returned invalid JSON: {e}")
                        raise UpdateFailed("API returned invalid response format")

                    # Validate response structure
                    if not isinstance(data, dict):
                        _LOGGER.warning(f"Expected dict response, got {type(data).__name__}")
                        raise UpdateFailed(f"Unexpected API response type: {type(data).__name__}")

                    # Debug: Log the full API response
                    _LOGGER.debug("Marstek API response: %s", data)

                    # Extract response code
                    code = data.get("code")

                    # Handle token expiration or invalid token (codes: -1, 401, 403)
                    if code in (-1, "-1", 401, "401", 403, "403"):
                        _LOGGER.warning(f"Marstek: Token expired or invalid (code {code}), refreshing...")
                        await self._get_token()
                        params["token"] = self._token

                        # Retry with new token
                        try:
                            async with self._session.get(API_DEVICES, params=params) as retry_resp:
                                if retry_resp.status != 200:
                                    _LOGGER.warning(f"Retry failed with HTTP {retry_resp.status}")
                                    raise UpdateFailed(f"API retry failed (HTTP {retry_resp.status})")

                                try:
                                    data = await retry_resp.json()
                                except (ValueError, aiohttp.ContentTypeError) as e:
                                    _LOGGER.warning(f"Invalid JSON on retry: {e}")
                                    raise UpdateFailed("API retry returned invalid response")

                                _LOGGER.debug("Marstek API response (after retry): %s", data)

                        except aiohttp.ClientError as e:
                            _LOGGER.warning(f"Network error during retry: {e}")
                            raise UpdateFailed(f"Network error on retry: {e}")

                    # Handle specific error code 8 (no access permission)
                    if str(data.get("code")) == "8":
                        _LOGGER.warning("Marstek: No access permission (code 8). Token cleared, will retry on next update.")
                        self._token = None
                        raise UpdateFailed("API access denied (code 8) - account may not have API permissions")

                    # Check for "data" field in response
                    if "data" not in data:
                        error_msg = data.get("msg") or data.get("message", "Unknown error")
                        error_code = data.get("code", "unknown")
                        _LOGGER.warning(f"API response missing 'data' field (code {error_code}): {error_msg}")
                        raise UpdateFailed(f"Invalid API response: {error_msg}")

                    # Validate data field is a list
                    if not isinstance(data["data"], list):
                        _LOGGER.warning(f"Expected list in 'data' field, got {type(data['data']).__name__}")
                        raise UpdateFailed("Invalid API response structure")

                    # Filter out ignored device types
                    all_devices = data["data"]
                    filtered_devices = [
                        device for device in all_devices
                        if device.get("type") not in IGNORED_DEVICE_TYPES
                    ]

                    # Log filtering results
                    filtered_count = len(all_devices) - len(filtered_devices)
                    if filtered_count > 0:
                        _LOGGER.debug(
                            "Filtered out %d device(s) with ignored types %s",
                            filtered_count,
                            IGNORED_DEVICE_TYPES
                        )

                    _LOGGER.debug(f"Retrieved {len(filtered_devices)} device(s) from Marstek API")
                    return filtered_devices

        except asyncio.TimeoutError:
            _LOGGER.warning("Marstek device list request timed out after 10 seconds - will retry")
            raise UpdateFailed("API request timeout - check network connection")
        except aiohttp.ClientError as e:
            _LOGGER.warning(f"Network error while fetching devices: {e} - will retry")
            raise UpdateFailed(f"Network error: {e}")
        except UpdateFailed:
            # Re-raise UpdateFailed exceptions (already logged above)
            raise
        except Exception as e:
            # Catch any unexpected errors (these are truly unexpected)
            _LOGGER.error(f"Unexpected error fetching devices: {e}", exc_info=True)
            raise UpdateFailed(f"Unexpected error: {e}")

class MarstekCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api: MarstekAPI, scan_interval: int):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Marstek Cloud",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.last_latency = None

    async def _async_update_data(self):
        start = time.perf_counter()
        devices = await self.api.get_devices()
        self.last_latency = round((time.perf_counter() - start) * 1000, 1)
        
        # Debug: Log the processed device data
        _LOGGER.debug("Marstek processed device data: %s", devices)
        _LOGGER.debug("Marstek API latency: %s ms", self.last_latency)
        
        return devices
