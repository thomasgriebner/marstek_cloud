# Claude.md – AI Development Guidelines for Marstek Cloud Integration

This document provides comprehensive guidelines for Claude and other AI assistants working on the Marstek Cloud Battery custom integration for Home Assistant. **The primary focus is on safe, cautious development to protect user data, ensure system stability, and maintain code quality.**

---

## Project Overview

**Marstek Cloud Battery Integration** is a Home Assistant custom component that connects Marstek battery systems to Home Assistant via the Marstek cloud API. It exposes real-time battery metrics as sensor entities.

- **Technology Stack**: Python 3, aiohttp, Home Assistant Core APIs
- **Integration Type**: Cloud polling (HACS-compatible)
- **API Provider**: Marstek Cloud API (eu.hamedata.com)
- **Key Features**: Token-based authentication, data coordinator pattern, diagnostic sensors, device registry integration

### Core Components

| File | Purpose |
|------|---------|
| `__init__.py` | Integration initialization, API client setup, coordinator creation |
| `config_flow.py` | User configuration flow (credentials, scan interval, battery capacity) |
| `coordinator.py` | Data update coordinator, API client, token management |
| `sensor.py` | Sensor entity definitions (battery metrics, diagnostics, totals) |
| `const.py` | Constants (API endpoints, defaults, ignored device types) |
| `manifest.json` | Integration metadata for Home Assistant |

---

## Critical Safety Rules for AI Development

### 1. Authentication & Security

**NEVER** modify authentication logic without thorough review:

- ✅ **DO**: Preserve existing MD5 password hashing for API compatibility
- ✅ **DO**: Store credentials securely using Home Assistant's config entries
- ✅ **DO**: Sanitize logs to prevent credential leakage
- ❌ **DON'T**: Change password hashing algorithms without API documentation
- ❌ **DON'T**: Log tokens, passwords, or email addresses
- ❌ **DON'T**: Store credentials in plaintext files or comments

**Token Handling Rules:**
- Tokens must be cached and reused until expired
- Token refresh must be automatic and transparent to the user
- Token errors must be handled gracefully with retry logic
- Never expose tokens in entity attributes or logs

### 2. API Interaction Safety

**ALWAYS** protect against API changes and failures:

- ✅ **DO**: Validate API responses before processing
- ✅ **DO**: Implement timeouts for all HTTP requests (default: 10 seconds)
- ✅ **DO**: Handle rate limiting gracefully
- ✅ **DO**: Respect the configured scan interval (10-3600 seconds)
- ✅ **DO**: Use `.get()` for ALL dictionary access to API data with sensible fallbacks
- ✅ **DO**: Wrap all API calls in try-except blocks for network errors
- ✅ **DO**: Check HTTP status codes before processing response
- ✅ **DO**: Validate response data types (dict, list, etc.)
- ❌ **DON'T**: Assume API response structure is stable
- ❌ **DON'T**: Make requests more frequently than configured
- ❌ **DON'T**: Ignore HTTP error codes or exceptions
- ❌ **DON'T**: Modify API endpoints without verifying compatibility
- ❌ **DON'T**: Use direct dictionary access (`device["field"]`) - always use `.get("field", default)`

**Required error handling for all API calls:**
```python
try:
    async with async_timeout.timeout(10):
        async with self._session.get(url, params=params) as resp:
            # 1. Check HTTP status
            if resp.status >= 500:
                raise UpdateFailed(f"Server error (HTTP {resp.status})")
            elif resp.status != 200:
                _LOGGER.warning(f"Non-200 status: {resp.status}")

            # 2. Parse JSON with error handling
            try:
                data = await resp.json()
            except (ValueError, aiohttp.ContentTypeError) as e:
                raise UpdateFailed("Invalid JSON response")

            # 3. Validate response structure
            if not isinstance(data, dict):
                raise UpdateFailed(f"Expected dict, got {type(data)}")

            # 4. Process data...

except asyncio.TimeoutError:
    _LOGGER.error("Request timed out")
    raise UpdateFailed("Timeout - check network")
except aiohttp.ClientError as e:
    _LOGGER.error(f"Network error: {e}")
    raise UpdateFailed(f"Network error: {e}")
except UpdateFailed:
    raise
except Exception as e:
    _LOGGER.error(f"Unexpected error: {e}", exc_info=True)
    raise UpdateFailed(f"Unexpected error: {e}")
```

**API Error Code Handling:**
- Code `8` (no access permission): Clear cached token, log error, retry on next cycle
- Invalid/expired token: Refresh token automatically, retry once
- Network errors: Log error, mark connection as offline, continue without crashing

### 3. Data Coordinator Pattern Compliance

**NEVER** bypass Home Assistant's data coordinator pattern:

- ✅ **DO**: Use `DataUpdateCoordinator` for all data fetching
- ✅ **DO**: Let entities pull data from the coordinator's cache
- ✅ **DO**: Handle `UpdateFailed` exceptions properly
- ✅ **DO**: Update all entities atomically when new data arrives
- ❌ **DON'T**: Make API calls directly from entity classes
- ❌ **DON'T**: Create multiple coordinators for the same data
- ❌ **DON'T**: Block the event loop with synchronous I/O
- ❌ **DON'T**: Update entities individually (use coordinator broadcasts)

### 4. Entity Creation and unique_id

**CRITICAL: Trust Home Assistant's entity registry for deduplication**

- ✅ **DO**: Assign stable `unique_id` to every entity
- ✅ **DO**: Base `unique_id` on device hardware ID (not user-changeable name)
- ✅ **DO**: Let `async_add_entities()` handle duplicate prevention
- ✅ **DO**: Validate data before creating entities
- ❌ **DON'T**: Manually check for duplicate entities
- ❌ **DON'T**: Use `hass.states.async_entity_ids()` for duplicate checking
- ❌ **DON'T**: Change `unique_id` format between versions (breaks entity registry)
- ❌ **DON'T**: Base `unique_id` on user-configurable values

**Why manual duplicate checking is wrong:**

Home Assistant's entity platform (`async_add_entities()`) automatically:
1. Checks if an entity with the same `unique_id` exists in the registry
2. Reuses the existing `entity_id` if found (maintains user customizations)
3. Prevents duplicate entities from being added
4. Logs errors if duplicates are attempted

**Correct pattern:**
```python
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Validate data exists
    if not coordinator.data:
        _LOGGER.warning("No data available")
        return

    entities = []

    for device in coordinator.data:
        devid = device.get("devid", "unknown")

        # Validate device
        if not devid or devid == "unknown":
            _LOGGER.warning(f"Skipping invalid device")
            continue

        # Create entities - NO duplicate checking needed!
        entities.append(MySensor(coordinator, device, ...))

    # Home Assistant handles deduplication automatically
    if entities:
        async_add_entities(entities)
```

**Wrong pattern (DO NOT USE):**
```python
# ❌ WRONG - This doesn't work!
existing = hass.states.async_entity_ids()  # Returns entity_ids
unique_id = "device123_sensor"              # Different format
if unique_id not in existing:               # Never matches!
    entities.append(MySensor(...))
```

**unique_id format rules:**
- Format: `{device_hardware_id}_{sensor_type}`
- Example: `SN12345_soc`, `devid789_charge_power`
- Must remain stable across restarts and updates
- Never use device name (user can rename it)

### 5. Backward Compatibility

**ALWAYS** maintain compatibility with existing installations:

- ✅ **DO**: Preserve existing config entry keys and structure
- ✅ **DO**: Provide migration logic for config changes
- ✅ **DO**: Support existing entity unique IDs
- ✅ **DO**: Test upgrades from previous versions
- ❌ **DON'T**: Remove config options without deprecation path
- ❌ **DON'T**: Change entity unique IDs (breaks user customizations)
- ❌ **DON'T**: Rename domains or platforms without migration
- ❌ **DON'T**: Break existing automations or dashboards

### 5. Device Type Filtering

**RESPECT** the device filtering logic:

- The integration filters out incompatible device types (see `IGNORED_DEVICE_TYPES` in `const.py`)
- Currently ignored: `["HME-3"]`
- ✅ **DO**: Filter devices early in the data flow (coordinator level)
- ✅ **DO**: Log filtered devices at DEBUG level for troubleshooting
- ❌ **DON'T**: Remove filtering without understanding device compatibility
- ❌ **DON'T**: Create entities for filtered device types

---

## Development Workflow

### Before Making Changes

1. **Read the relevant files completely** before proposing changes
2. **Understand the data flow**: config_flow → __init__ → coordinator → sensor
3. **Check existing issues** on GitHub for known bugs or feature requests
4. **Test in a Home Assistant instance** if possible (not just code review)

### When Modifying Code

1. **Preserve existing functionality** unless explicitly asked to change it
2. **Add logging** at appropriate levels (see detailed guidelines below)
3. **Handle exceptions** at the appropriate level:
   - Coordinator: Raise `UpdateFailed` for API errors
   - Config flow: Show user-friendly error messages
   - Init: Log errors and return `False` on setup failure
4. **Validate inputs**:
   - Scan interval: 10-3600 seconds
   - Battery capacity: positive float (kWh)
   - Email: non-empty string
   - Password: non-empty string

### Testing Requirements

**BEFORE** committing changes:

1. **Syntax validation**: Ensure code passes Home Assistant's validation
2. **Manual testing**: Test in a real Home Assistant instance if possible
3. **Edge cases**: Test with missing data, API errors, token expiration
4. **Upgrade path**: Test upgrade from previous version
5. **Config flow**: Test both initial setup and options flow
6. **Diagnostics**: Verify diagnostic sensors report correct status

**Required test scenarios:**
- Initial setup with valid credentials
- Initial setup with invalid credentials
- Token expiration and refresh
- API unavailable (network error)
- Device filtering (if device list includes ignored types)
- Scan interval modification via options
- Battery capacity modification via options

---

## Git Commit Guidelines

**Commit message requirements:**

1. **Language**: ALL commit messages MUST be in English
2. **No AI attribution**: Do NOT include any references to AI, Claude, or AI-assisted development
3. **No co-author tags**: Do NOT add "Co-Authored-By: Claude" or similar attribution
4. **Format**: Use conventional commit format when appropriate:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `refactor:` for code refactoring
   - `docs:` for documentation changes
   - `chore:` for maintenance tasks
   - `test:` for test additions/modifications

**Example commit messages:**

✅ **Good:**
```
feat: simplify sensor naming by removing device prefix

Sensor names now show only the metric name (e.g., "State of Charge")
instead of including the device name, as device association is handled
via the device registry.
```

✅ **Good:**
```
fix: handle token expiration gracefully

Add automatic token refresh when API returns error code 8.
Prevents integration from failing on expired tokens.
```

❌ **Bad:**
```
Update sensor names

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

❌ **Bad:**
```
Sensor Namen vereinfachen
```

**Important:** When creating commits, focus on clear, descriptive messages that explain WHAT changed and WHY, without mentioning how the change was made (AI-assisted or otherwise).

---

## Code-Specific Guidelines

### Sensor Entities

**Naming conventions:**
- Sensor name: `{device_name} {metric_name}` (e.g., "Battery1 State of Charge")
- ALWAYS include device name in sensor name for proper Home Assistant integration
- Unique ID: `{devid}_{field_name}` (must remain stable for entity registry)
- Entity ID: Auto-generated by Home Assistant based on device and sensor name

**Rationale for device name prefix:**
- Home Assistant automatically handles context-aware display:
  - On device detail page: Shows only "State of Charge" (device context is implicit)
  - In rooms/dashboards: Shows "Battery1 State of Charge" (multiple devices need disambiguation)
  - In entity lists: Shows full name for clarity
- This is Home Assistant best practice for multi-device integrations
- Example: Use `f"{device['name']} {meta['name']}"` in sensor initialization

**Required attributes:**
- `device_info`: Link entity to device in registry (enables Home Assistant's smart name display)
- `native_value`: The sensor's current value
- `native_unit_of_measurement`: Unit (if applicable)
- `device_class`: Standard Home Assistant device class (if applicable)
- `state_class`: `measurement` or `total_increasing` (for energy sensors)

**Important:** The combination of full sensor names (`device_name + metric_name`) and proper `device_info` linkage allows Home Assistant to intelligently display names based on context. Do not use simple names without device prefix.

**Device classes to use:**
- `soc`: `SensorDeviceClass.BATTERY`
- `charge`/`discharge`/`load`: `SensorDeviceClass.POWER`
- `total_charge`: `SensorDeviceClass.ENERGY`
- `profit`: `SensorDeviceClass.MONETARY`

### Config Flow

**User experience rules:**
- Show clear error messages for authentication failures
- Validate inputs before attempting API calls
- Provide sensible defaults (scan interval: 60s, capacity: 5.12 kWh)
- Allow reconfiguration via options flow
- Show progress indicators for slow operations

**Error messages must be:**
- User-friendly (avoid technical jargon)
- Actionable (explain what the user should do)
- Specific (don't just say "error occurred")

### Coordinator Updates

**Update cycle rules:**
- Record start time for latency calculation
- Fetch data from API with proper error handling
- Filter ignored device types
- Calculate latency in milliseconds
- Return structured data (list of devices)
- Update `last_update` timestamp on success
- Update `connection_status` based on API response

**Error handling:**
- Raise `UpdateFailed` with descriptive message
- Log full exception details at DEBUG level
- Preserve previous data on transient errors
- Mark connection as offline on network errors

---

## Defensive Programming Rules

### Critical: Always Use .get() for API Data

**NEVER use direct dictionary access for API response data:**

❌ **Wrong:**
```python
device_name = device["name"]
devid = device["devid"]
soc = dev["soc"]
```

✅ **Correct:**
```python
device_name = device.get("name", f"Device {device.get('devid', 'unknown')}")
devid = device.get("devid", "unknown")
soc = dev.get("soc", 0)
```

**Rationale:**
- API responses may change over time
- Network issues can cause incomplete data
- Different device types may have different fields
- Graceful degradation is better than crashes

**Fallback value guidelines:**
- `devid`: Use `"unknown"` (required for unique IDs)
- `name`: Use `f"Device {devid}"` or `f"Marstek {devid}"`
- `type`: Use `"Unknown"`
- `version`: Use `"Unknown"` (for sw_version)
- `sn`: Use `""` (empty string for serial number)
- Numeric values (`soc`, `charge`, etc.): Use `0`
- `capacity_kwh`: Use `DEFAULT_CAPACITY_KWH` constant

---

## Logging Guidelines

**CRITICAL: Choose appropriate log levels to avoid log spam**

Cloud APIs can have temporary issues. Use log levels intelligently:

### ERROR (User must take action)
Use ERROR only when the user needs to fix something:
- ❌ Invalid credentials (401) - user must update password
- ❌ Unexpected exceptions - code bug that needs fixing

**Example:**
```python
_LOGGER.error("Marstek login failed: Invalid credentials (HTTP 401)")
_LOGGER.error(f"Unexpected error fetching devices: {e}", exc_info=True)
```

### WARNING (Temporary issues, will auto-retry)
Use WARNING for transient problems that will resolve automatically:
- ⚠️ Server errors (500+) - Marstek API is temporarily down
- ⚠️ Timeouts - network congestion or slow API
- ⚠️ Invalid JSON - temporary API glitch
- ⚠️ Token expired - will be refreshed automatically
- ⚠️ Network errors - temporary connectivity issues
- ⚠️ No API access (code 8) - token cleared, will retry with new token

**Example:**
```python
_LOGGER.warning(f"Marstek API temporarily unavailable (HTTP {resp.status}) - will retry")
_LOGGER.warning("Marstek device list request timed out after 10 seconds - will retry")
_LOGGER.warning(f"Network error while fetching devices: {e} - will retry")
_LOGGER.warning(f"Marstek: Token expired or invalid (code {code}), refreshing...")
_LOGGER.warning("Marstek: No access permission (code 8). Token cleared, will retry on next update.")
```

### INFO (Normal operations)
Use INFO for successful important operations:
- ✅ Token obtained successfully
- ✅ Integration setup completed
- ✅ Configuration reloaded

**Example:**
```python
_LOGGER.info("Marstek: Obtained new API token")
_LOGGER.info(f"Marstek setup completed with {len(coordinator.data)} devices")
```

### DEBUG (Detailed troubleshooting info)
Use DEBUG for detailed information useful during troubleshooting:
- 🔍 Full API responses
- 🔍 Filtered device counts
- 🔍 API latency measurements
- 🔍 Processed device data

**Example:**
```python
_LOGGER.debug("Marstek API response: %s", data)
_LOGGER.debug(f"Retrieved {len(filtered_devices)} device(s) from Marstek API")
_LOGGER.debug(f"Filtered out {count} device(s) with ignored types")
```

### Log Level Decision Tree

```
Is this a problem?
├─ NO → Use INFO (success) or DEBUG (details)
└─ YES → Can the system recover automatically?
    ├─ YES → Use WARNING (e.g., timeout, server error)
    └─ NO → Does the user need to fix it?
        ├─ YES → Use ERROR (e.g., invalid credentials, no API access)
        └─ NO → Use ERROR with exc_info=True (unexpected bug)
```

**Important:** The DataUpdateCoordinator already adds context like "Error fetching Marstek Cloud data:" to UpdateFailed messages. Your log message should focus on the specific problem, not repeat this context.

---

## Common Pitfalls to Avoid

### 1. Async/Await Mistakes
- ❌ Calling async functions without `await`
- ❌ Using blocking I/O in async functions
- ❌ Not using `async_add_executor_job` for sync operations
- ✅ Always `await` async API calls
- ✅ Use `aiohttp` for HTTP requests (never `requests`)

### 2. Entity State Updates
- ❌ Calling `async_write_ha_state()` in tight loops
- ❌ Updating entities directly outside coordinator updates
- ❌ Storing coordinator reference incorrectly
- ✅ Let coordinator trigger entity updates via `async_update_listeners()`
- ✅ Access coordinator data in `native_value` property

### 3. Device Registry
- ❌ Creating devices without proper identifiers
- ❌ Changing device identifiers (breaks device registry)
- ❌ Missing manufacturer, model, or name
- ✅ Use consistent device identifiers (serial number)
- ✅ Update device info on firmware version changes

### 4. Configuration Changes
- ❌ Not implementing `async_unload_entry()` properly
- ❌ Forgetting to reload entry after options change
- ❌ Not cleaning up resources on unload
- ✅ Implement full setup/teardown cycle
- ✅ Close aiohttp sessions on unload

---

## API Documentation Reference

### Login Endpoint
```
POST https://eu.hamedata.com/app/Solar/v2_get_device.php?pwd={MD5_PASSWORD}&mailbox={EMAIL}

Response:
{
  "code": "0",
  "msg": "success",
  "token": "abc123...",
  ...
}
```

### Device List Endpoint
```
GET https://eu.hamedata.com/ems/api/v1/getDeviceList?token={TOKEN}

Response:
{
  "code": "0",
  "msg": "success",
  "list": [
    {
      "devid": "...",
      "sn": "...",
      "type": "...",
      "soc": 85,
      "charge": 1500,
      "discharge": 0,
      ...
    }
  ]
}
```

**Error Codes:**
- `0`: Success
- `8`: No access permission (token invalid/expired)
- Other codes: Specific API errors (check API logs)

---

## When to Ask for Clarification

**ALWAYS** ask the user before:

1. Changing authentication or token management logic
2. Modifying API endpoints or request structure
3. Changing entity unique IDs or names
4. Removing existing features or sensors
5. Changing default values (scan interval, capacity)
6. Adding new dependencies to `manifest.json`
7. Implementing breaking changes to config structure
8. Modifying device filtering rules

**NEVER** assume:

- API response structure will always match current format
- All devices support all metrics
- Token validity period
- User's network is reliable
- Home Assistant version compatibility without checking

---

## Home Assistant Best Practices

1. **Use Core APIs**: Leverage Home Assistant's built-in helpers and utilities
2. **Follow ADR**: Reference Home Assistant Architecture Decision Records
3. **Type hints**: Use Python type hints for all function signatures
4. **Logging**: Use structured logging with proper severity levels
5. **Translations**: Support i18n for user-facing strings (use `strings.json`)
6. **Documentation**: Keep docstrings up to date
7. **Validation**: Use Home Assistant's validation GitHub Actions

---

## Helpful Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/)
- [DataUpdateCoordinator Docs](https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities)
- [Config Flow Tutorial](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [HACS Requirements](https://hacs.xyz/docs/publish/integration)

---

## Version History

- **0.3.0**: HACS support, device class additions, validation fixes
- **0.2.x**: Device filtering, diagnostic sensors, cross-device totals
- **0.1.x**: Initial release with basic sensor support

---

## Summary for AI Assistants

**Core Principle: Safety First**

When working on this integration:
1. Read existing code before proposing changes
2. Preserve authentication and token handling logic
3. Respect the data coordinator pattern
4. Maintain backward compatibility
5. Test thoroughly before committing
6. Ask for clarification when uncertain
7. Prioritize user data security and system stability

**This integration handles user credentials and interacts with external APIs. Exercise extreme caution when modifying authentication, API calls, or data handling logic. When in doubt, ask the user for clarification rather than making assumptions.**
