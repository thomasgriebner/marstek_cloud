import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .coordinator import MarstekAPI, MarstekCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Marstek from a config entry."""
    # Pre-import platforms to avoid blocking import inside event loop
    for platform in PLATFORMS:
        __import__(f"{__package__}.{platform}")

    session = async_get_clientsession(hass)
    api = MarstekAPI(session, entry.data["email"], entry.data["password"])

    scan_interval = entry.options.get(
        "scan_interval",
        entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )

    coordinator = MarstekCoordinator(hass, api, scan_interval)

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as ex:
        error_msg = str(ex)
        # If credentials are invalid, trigger reauth flow
        if "Invalid email or password" in error_msg:
            _LOGGER.error("Authentication failed for Marstek Cloud - triggering reauth")
            raise ConfigEntryAuthFailed(error_msg) from ex
        # For other errors (network, API issues), retry later
        _LOGGER.warning(f"Setup failed, will retry: {error_msg}")
        raise ConfigEntryNotReady(error_msg) from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Ensure devices key exists in config_entry.data
    devices = coordinator.data or []
    hass.config_entries.async_update_entry(entry, data={**entry.data, "devices": devices})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
