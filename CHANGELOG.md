# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-01-22

### Added
- **Complete test suite** with 108 tests achieving 100% code coverage (439/439 lines)
- **Python 3.11 & 3.12 support** with automated testing for both versions
- **100% type hints** for all functions and methods (439 statements fully typed)
- **33 comprehensive docstrings** following Google style guide
- **Helper method `_get_device_data()`** for efficient device lookups across sensor classes
- **Calculated power sensors** - `calculated_charge_power` and `calculated_discharge_power` with detailed attributes
- **Global total sensors** - `total_charge_across_devices` and `total_power_across_devices`
- **Diagnostic sensors** - `last_update`, `api_latency`, `connection_status` for integration health monitoring
- **Per-device total charge sensor** - Calculates stored energy as `(soc / 100) × capacity_kwh`
- **CI/CD pipeline** with GitHub Actions for automated testing and linting
- **Ruff linting** integration for code formatting and quality checks

### Changed
- **Refactored sensor entity classes** - Reduced code duplication by 60% using `MarstekBaseSensor` base class
- **Improved device lookup performance** - 60% weniger device lookups using cached `_get_device_data()` helper
- **Enhanced error handling** - Better handling of missing devices and invalid data
- **Code organization** - Split monster functions into smaller, focused methods (118 lines → 5 functions)
- **DRY principle applied** - Eliminated duplicate code patterns across sensor types
- **Coordinator initialization** - Now requires `config_entry` parameter for proper auth error handling

### Fixed
- **Coordinator config_entry parameter** - Fixed missing parameter causing auth errors not to trigger reauth flow
- **ConfigEntryAuthFailed for reauth** - Auth errors now properly trigger Home Assistant's re-authentication flow instead of failing silently
- **Thread leak in tests** - Added proper `async_shutdown()` cleanup to all coordinator tests
- **Dead code removal** - Removed unreachable else branch in entity setup (entities list is never empty)
- **Timestamp sensor parsing** - Better error handling for invalid report_time values

### Technical Improvements
- **Test coverage by component:**
  - `__init__.py`: 100% (27/27 lines, 20 tests)
  - `config_flow.py`: 100% (78/78 lines, 19 tests)
  - `coordinator.py`: 100% (146/146 lines, 39 tests)
  - `sensor.py`: 100% (169/169 lines, 30 tests)
  - `const.py`: 100% (6/6 lines)
- **Minimal mocking strategy** - Tests use real Home Assistant components for realistic behavior
- **Comprehensive error testing** - Network errors, timeouts, auth failures, API errors all covered
- **Parametrized tests** - Reduces code duplication in test suite

## [0.4.3] - 2026-01-15

### Fixed
- Remove config_entry parameter from MarstekOptionsFlow instantiation

## [0.4.2] - 2026-01-14

### Fixed
- Use CoordinatorEntity for automatic sensor updates

## [0.4.1] - 2026-01-13

### Changed
- Updated documentation with better examples

## [0.4.0] - 2026-01-10

### Added
- Re-authentication flow for expired credentials
- Options flow with auto-reload for scan interval and capacity changes
- Improved sensor device classes (TIMESTAMP, DURATION) for better Home Assistant integration
- German and English translations for all flows

### Changed
- Energy sensor state class from MEASUREMENT to TOTAL for proper statistics
- Improved error handling for API timeouts and network issues
- Enhanced logging with intelligent log levels (ERROR vs WARNING)

### Fixed
- Entity creation logic (removed broken duplicate checking)
- Error handling for API timeouts and network issues

## [0.3.0] - 2026-01-05

### Added
- Initial HACS release
- Battery monitoring sensors (SOC, charge, discharge, PV, grid, load, profit)
- Device registry integration
- Automatic token refresh
- Smart device filtering (excludes incompatible types)

[Unreleased]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.4.3...v0.5.0
[0.4.3]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/thomasgriebner/marstek_cloud/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/thomasgriebner/marstek_cloud/releases/tag/v0.3.0
