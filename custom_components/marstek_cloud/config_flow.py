import logging
import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_CAPACITY_KWH
from .coordinator import MarstekAPI

_LOGGER = logging.getLogger(__name__)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

DATA_SCHEMA = vol.Schema({
    vol.Required("email"): str,
    vol.Required("password"): str,
    vol.Required(
        "scan_interval",
        default=DEFAULT_SCAN_INTERVAL
    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
    vol.Optional("default_capacity_kwh", default=5.12): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=100))
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input by testing API connection.

    This function creates a temporary API instance and attempts to fetch devices
    to verify that the credentials are valid and the user has API access.

    Args:
        hass: Home Assistant instance
        data: User input data containing email and password

    Returns:
        dict: Information about the validated connection (title)

    Raises:
        InvalidAuth: If credentials are invalid (HTTP 401)
        CannotConnect: If unable to connect to API (network, timeout, server error)
    """
    session = async_get_clientsession(hass)
    api = MarstekAPI(session, data["email"], data["password"])

    try:
        # Attempt to fetch devices - this validates credentials and API access
        devices = await api.get_devices()
        _LOGGER.debug(f"Credential validation successful, found {len(devices)} device(s)")

        # Return info for config entry title
        return {"title": f"Marstek Cloud ({data['email']})"}

    except UpdateFailed as ex:
        error_msg = str(ex)
        _LOGGER.warning(f"Credential validation failed: {error_msg}")

        # Map MarstekAPI errors to Home Assistant exceptions
        if "Invalid email or password" in error_msg:
            raise InvalidAuth(error_msg) from ex
        else:
            # All other UpdateFailed errors are connectivity issues
            raise CannotConnect(error_msg) from ex

class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek Cloud."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial user configuration step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate credentials by attempting API connection
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during credential validation")
                errors["base"] = "unknown"
            else:
                # Validation successful - create config entry
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        "email": user_input["email"],
                        "password": user_input["password"],
                        "scan_interval": user_input["scan_interval"],
                        "default_capacity_kwh": user_input.get("default_capacity_kwh", DEFAULT_CAPACITY_KWH)
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reauth(self, entry_data=None):
        """Handle reauth flow when credentials expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm reauth with new credentials."""
        config_entry = self._get_reauth_entry()
        errors = {}

        if user_input is not None:
            try:
                # Validate new credentials
                await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth validation")
                errors["base"] = "unknown"
            else:
                # Validation successful - update config entry
                return self.async_update_reload_and_abort(
                    config_entry,
                    data={**config_entry.data, **user_input},
                    reason="reauth_successful"
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required("email", default=config_entry.data.get("email")): str,
                vol.Required("password"): str,
            }),
            errors=errors,
            description_placeholders={
                "email": config_entry.data.get("email", "")
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MarstekOptionsFlow()


class MarstekOptionsFlow(OptionsFlowWithReload):
    """Handle options flow for Marstek integration - auto-reloads on save."""

    async def async_step_init(self, user_input=None):
        """Manage the options for the integration."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Generate a schema for editing scan_interval and capacity_kwh for each battery
        options = self.config_entry.options
        data_schema = {}

        # Add scan_interval as first option
        data_schema[vol.Optional(
            "scan_interval",
            default=options.get(
                "scan_interval",
                self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            )
        )] = vol.All(vol.Coerce(int), vol.Range(min=10, max=3600))

        # Handle missing devices key gracefully
        devices = self.config_entry.data.get("devices", [])
        if not devices:
            return self.async_abort(reason="no_devices_found")

        # Add capacity_kwh for each battery
        for device in devices:
            devid = device.get("devid", "unknown")
            name = device.get("name", f"Device {devid}")
            description = f"Set the capacity (in kWh) for {name}"  # Add description for each option
            data_schema[vol.Optional(
                f"{devid}_capacity_kwh",
                default=options.get(f"{devid}_capacity_kwh", DEFAULT_CAPACITY_KWH),
                description={"suggested_value": DEFAULT_CAPACITY_KWH, "description": description}
            )] = vol.Coerce(float)

        return self.async_show_form(step_id="init", data_schema=vol.Schema(data_schema))
