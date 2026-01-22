"""Constants for the Marstek Cloud integration."""

DOMAIN = "marstek_cloud"
API_LOGIN = "https://eu.hamedata.com/app/Solar/v2_get_device.php"
API_DEVICES = "https://eu.hamedata.com/ems/api/v1/getDeviceList"

# Default configuration values
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_CAPACITY_KWH = 5.12

# API timeout values (in seconds)
API_TIMEOUT = 10
API_RETRY_TIMEOUT = 10

# List of device types to ignore in API responses
IGNORED_DEVICE_TYPES = ["HME-3"]

# HTTP status codes for token expiration/invalid token
TOKEN_INVALID_CODES = {-1, "-1", 401, "401", 403, "403"}
