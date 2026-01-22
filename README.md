# Marstek Cloud - Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/home%20assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![GitHub Release](https://img.shields.io/github/v/release/thomasgriebner/marstek_cloud)](https://github.com/thomasgriebner/marstek_cloud/releases)

Connect your Marstek battery system to Home Assistant and take control of your energy. Monitor battery levels, track power flows, optimize energy usage, and save money on electricity - all from your Home Assistant dashboard.

**Why Choose This Integration:**
- 🔋 **Real-time Battery Monitoring** - See your battery status at a glance
- 📊 **Energy Dashboard Integration** - Beautiful visualizations of power flows
- 🔄 **Automatic Updates** - Set it and forget it, no manual polling
- 💰 **Track Your Savings** - Monitor profit and optimize energy usage
- 🚀 **2-Minute Setup** - Easy configuration via Home Assistant UI
- 🛡️ **Reliable** - Tested and production-ready

---

## What Can You Do?

### 🔋 Monitor Your Energy in Real-Time

See everything about your Marstek battery system:
- **Battery Level** - Current charge percentage and stored energy (kWh)
- **Power Flows** - Live view of charging, discharging, solar production, grid usage, and home consumption
- **Energy Statistics** - Track total energy stored across all your batteries
- **System Health** - See when data was last updated and connection status

### 💰 Save Money on Electricity

Make smart decisions about your energy:
- **Profit Tracking** - See how much money your battery system is saving
- **Optimize Usage** - Create automations based on battery level and electricity prices
- **Peak Shaving** - Avoid expensive grid electricity during peak hours
- **Smart Charging** - Charge during cheap off-peak times, discharge during expensive peaks

### 📈 Beautiful Dashboards

Integrate with Home Assistant's powerful visualization features:
- **Energy Dashboard** - Official Home Assistant energy dashboard support
- **Custom Cards** - Create stunning Lovelace dashboards with graphs and gauges
- **Historical Data** - Long-term statistics and trends
- **Mobile Access** - Monitor your battery from anywhere

### 🤖 Smart Automations

Create intelligent home automations:
- Turn on appliances when battery is full and sun is shining
- Get notified when battery is low
- Switch to battery power during expensive grid hours
- Optimize heating/cooling based on available solar energy

### 🔧 Easy Management

- **Automatic Updates** - Data syncs every minute (configurable)
- **Re-authentication** - Seamless credential updates if they change
- **Multi-Battery Support** - Manage multiple Marstek batteries
- **Device Integration** - Each battery appears as a proper Home Assistant device with all its sensors

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click the **three dots menu** → **Custom repositories**
3. Add `https://github.com/thomasgriebner/marstek_cloud` as an **Integration**
4. Click **Explore & Download Repositories** and search for **Marstek Cloud**
5. Click **Download**
6. **Restart Home Assistant**
7. Go to **Settings → Devices & Services → Add Integration** → Search **Marstek Cloud**

### Method 2: Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/thomasgriebner/marstek_cloud/releases)
2. Copy the `custom_components/marstek_cloud` folder to your Home Assistant `config/custom_components/` directory
3. **Restart Home Assistant**
4. Go to **Settings → Devices & Services → Add Integration** → Search **Marstek Cloud**

---

## Configuration

### Initial Setup

1. Navigate to **Settings → Devices & Services → Add Integration**
2. Search for **Marstek Cloud** and select it
3. Enter your **Marstek Cloud credentials**:
   - **Email** - Your Marstek Cloud account email
   - **Password** - Your Marstek Cloud password
4. Configure **Scan Interval** (10-3600 seconds, default: 60s)
   - How often the integration fetches data from the API
   - Lower values = more frequent updates but higher API load
5. Set **Default Battery Capacity** (default: 5.12 kWh)
   - Used to calculate total stored energy (SOC × Capacity)
   - Can be adjusted per battery later in Options
6. Click **Submit**

The integration validates your credentials before saving. If successful, all sensors will be created automatically.

### Configuration Options

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `email` | string | - | Required | Marstek Cloud account email |
| `password` | string | - | Required | Marstek Cloud account password |
| `scan_interval` | integer | 10-3600 | 60 | Update interval in seconds |
| `default_capacity_kwh` | float | > 0 | 5.12 | Default battery capacity in kWh |

### Options Flow (Reconfigure)

After initial setup, you can adjust settings via **Settings → Devices & Services → Marstek Cloud → Configure**:

- **Scan Interval** - Change update frequency (10-3600 seconds)
- **Battery Capacities** - Adjust capacity for each discovered battery individually
- Changes take effect **immediately** with automatic integration reload

### Re-authentication

If your credentials expire or change, Home Assistant will display a notification:

1. Click **Authenticate** in the notification, or go to **Settings → Devices & Services → Marstek Cloud**
2. Enter your **new credentials**
3. Click **Submit**

The integration continues working seamlessly without losing entity IDs, history, or automations.

---

## Entities

The integration creates multiple sensor entities for each battery device, plus global sensors.

### Per-Battery Sensors

Each configured Marstek battery provides the following sensors:

#### Battery Data Sensors
| Sensor | Entity ID Pattern | Unit | Device Class | Update Interval |
|--------|-------------------|------|--------------|-----------------|
| State of Charge | `sensor.<battery_name>_state_of_charge` | % | Battery | Scan Interval |
| Charge Power | `sensor.<battery_name>_charge_power` | W | Power | Scan Interval |
| Discharge Power | `sensor.<battery_name>_discharge_power` | W | Power | Scan Interval |
| Solar Power | `sensor.<battery_name>_solar_power` | W | Power | Scan Interval |
| Grid Power | `sensor.<battery_name>_grid_power` | W | Power | Scan Interval |
| Load Power | `sensor.<battery_name>_load_power` | W | Power | Scan Interval |
| Profit | `sensor.<battery_name>_profit` | € | Monetary | Scan Interval |
| Report Time | `sensor.<battery_name>_report_time` | - | Timestamp | Scan Interval |
| Firmware Version | `sensor.<battery_name>_firmware_version` | - | - | Scan Interval |
| Serial Number | `sensor.<battery_name>_serial_number` | - | - | Scan Interval |

#### Calculated Sensors
| Sensor | Entity ID Pattern | Unit | Formula | Description |
|--------|-------------------|------|---------|-------------|
| Calculated Charge Power | `sensor.<battery_name>_calculated_charge_power` | W | `max(0, pv - discharge)` | Actual charge power considering PV |
| Calculated Discharge Power | `sensor.<battery_name>_calculated_discharge_power` | W | `max(0, discharge - pv)` | Actual discharge power when PV insufficient |

**Attributes:** Both calculated sensors include:
- `pv_power` - Current PV power
- `discharge_power` - Current discharge power
- `raw_calculation` - Unfiltered calculation result
- `calculation_method` - Formula used

#### Energy Sensors
| Sensor | Entity ID Pattern | Unit | Formula | Description |
|--------|-------------------|------|---------|-------------|
| Total Charge | `sensor.<battery_name>_total_charge` | kWh | `(soc / 100) × capacity_kwh` | Stored energy in battery |

**Attributes:**
- `device_name` - Battery device name
- `capacity_kwh` - Configured battery capacity

#### Diagnostic Sensors
| Sensor | Entity ID Pattern | Unit | Category | Description |
|--------|-------------------|------|----------|-------------|
| Last Update | `sensor.<battery_name>_last_update` | - | Diagnostic | Timestamp of last successful update |
| API Latency | `sensor.<battery_name>_api_latency` | ms | Diagnostic | API response time |
| Connection Status | `sensor.<battery_name>_connection_status` | - | Diagnostic | online/offline |

### Global Sensors

These sensors aggregate data across all battery devices:

| Sensor | Entity ID | Unit | Formula | Description |
|--------|-----------|------|---------|-------------|
| Total Charge Across Devices | `sensor.total_charge_across_devices` | kWh | Sum of all battery total_charge | Total stored energy |
| Total Power Across Devices | `sensor.total_power_across_devices` | W | Sum of all (charge - discharge) | Net power flow |

**Attributes:** Both include `device_count` - Number of batteries

### Entity Naming

Entities are named based on the battery name configured in the Marstek Cloud system:
- Device name in Marstek Cloud: `Battery 1`
- Entity example: `sensor.battery_1_state_of_charge`

### Update Behavior

- All sensors update together when the coordinator refreshes (based on `scan_interval`)
- If API call fails, sensors retain last known values and show as `unavailable` after timeout
- Diagnostic sensors update on every coordinator refresh attempt (success or failure)

---

## How It Works

Simple and secure:

1. **Setup** - Enter your Marstek Cloud credentials in Home Assistant (same email and password as in the Marstek app)
2. **Authentication** - Integration connects securely to Marstek Cloud API
3. **Data Sync** - Battery data is fetched automatically every minute (you can change this to any interval between 10 seconds and 1 hour)
4. **Sensors** - All metrics appear as Home Assistant sensors
5. **Enjoy** - Use in dashboards, automations, or the Energy panel

**Privacy & Security:**
- Your credentials are stored securely in Home Assistant's encrypted storage
- All communication with Marstek Cloud is encrypted (HTTPS)
- No data is shared with third parties
- Works completely locally within your Home Assistant instance - only communicates with Marstek Cloud

**Internet Required:**
- This integration requires internet access to communicate with Marstek Cloud
- Your batteries must be connected to Marstek Cloud and showing data in the Marstek app
- If Marstek Cloud is down, sensors will show as unavailable until the service is back
- The integration automatically reconnects when the service is restored

**Supported Battery Types:**
- HME-5 series (and similar compatible Marstek battery systems)
- If your battery works with the Marstek Cloud app (eu.hamedata.com), it should work with this integration
- Some older device types may be automatically filtered if incompatible

---

## Troubleshooting

### Integration Setup Issues

#### "invalid_auth" error during setup
**Cause:** Incorrect email or password

**Solution:**
1. Verify your Marstek Cloud credentials at [eu.hamedata.com](https://eu.hamedata.com)
2. Ensure you're using the email address registered with Marstek Cloud
3. Check for typos in email/password
4. Try again with correct credentials

#### "cannot_connect" error during setup
**Cause:** Network issue or Marstek API temporarily unavailable

**Solution:**
1. Check your Home Assistant internet connection
2. Verify `eu.hamedata.com` is accessible from your network
3. Check for firewall or proxy blocking the connection
4. Wait a few minutes and try again
5. Check [Marstek status page](https://eu.hamedata.com) for API outages

#### "No devices found" error
**Cause:** No compatible battery devices in your Marstek Cloud account

**Solution:**
1. Log in to [Marstek Cloud](https://eu.hamedata.com) and verify your battery is registered
2. Ensure your device type is supported (HME-5, etc.)
3. Check device is online and reporting data in Marstek Cloud app
4. Some device types (e.g., "HME-3") are automatically filtered - verify compatibility

### Runtime Issues

#### Sensors show "unavailable"
**Cause:** API connection issues or integration not loaded

**Solution:**
1. Check Home Assistant logs: **Settings → System → Logs**
2. Look for errors from `custom_components.marstek_cloud`
3. Try reloading: **Settings → Devices & Services → Marstek Cloud → ⋮ → Reload**
4. Check internet connection
5. Verify Marstek Cloud API is accessible

#### Authentication notifications keep appearing
**Cause:** Credentials expired or changed in Marstek Cloud

**Solution:**
1. Click **Authenticate** in the notification
2. Enter your current Marstek Cloud credentials
3. If using HACS, ensure integration is up-to-date
4. If issue persists:
   - Remove integration: **Settings → Devices & Services → Marstek Cloud → Delete**
   - Re-add integration with current credentials

#### Sensors update slowly or not at all
**Cause:** Scan interval too high or API rate limiting

**Solution:**
1. Check current scan interval: **Settings → Devices & Services → Marstek Cloud → Configure**
2. Lower scan interval (minimum 10 seconds recommended)
3. Check API latency in diagnostic sensors (`sensor.<battery>_api_latency`)
4. If latency is high (>5000ms), consider increasing scan interval

#### Wrong battery capacity displayed
**Cause:** Incorrect capacity configuration

**Solution:**
1. Go to **Settings → Devices & Services → Marstek Cloud → Configure**
2. Adjust capacity for each battery individually
3. Changes apply immediately after saving

### Debug Logging

Enable detailed logging for troubleshooting:

1. Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.marstek_cloud: debug
```

2. Restart Home Assistant
3. Reproduce the issue
4. Check logs: **Settings → System → Logs**

**Log entries to look for:**
- `Token expired, refreshing...` - Normal token refresh
- `API error code 8` - Permission issues, check credentials
- `Invalid response from API` - API communication problem
- `Device filtering: excluded X devices` - Shows filtered devices

### Getting Help

If issues persist:

1. Check existing [GitHub Issues](https://github.com/thomasgriebner/marstek_cloud/issues)
2. Open a new issue with:
   - Home Assistant version
   - Integration version
   - Debug logs (remove sensitive data)
   - Steps to reproduce
3. Join [Home Assistant Community](https://community.home-assistant.io/) for community support

---

## Changelog

**Latest Release: 0.5.0** (2026-01-22)
- Complete test suite with 100% coverage for rock-solid reliability
- Enhanced error handling and automatic recovery
- New calculated sensors for accurate power tracking
- Global statistics across all batteries
- Performance improvements and bug fixes

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/thomasgriebner/marstek_cloud/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thomasgriebner/marstek_cloud/discussions)
- **Community**: [Home Assistant Community Forum](https://community.home-assistant.io/)

---

## License

This project is provided as-is under MIT License for personal and commercial use.

---

## Acknowledgments

- Home Assistant Community for excellent documentation and tools
- Marstek for their battery systems and cloud API
- All contributors who help improve this integration
