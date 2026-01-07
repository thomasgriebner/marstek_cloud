# Claude AI Agent - Arbeitsanweisungen

Dieses Dokument definiert die Arbeitsweise des AI Agents für die Marstek Cloud Integration.

## 🤖 Automatische Aktionen

### TRIGGER: Commit-Anfrage
**Wenn der Entwickler sagt:**
- "Ich will committen"
- "Commit das"
- "Lass uns committen"
- "Push das"

**DANN führe ich AUTOMATISCH aus:**
1. Vollständigen Code-Review (siehe Checkliste unten)
2. Report mit GO/NO-GO Entscheidung
3. Bei NO-GO: Liste der zu behebenden Issues
4. Bei GO: Commit-Message-Vorschlag

### TRIGGER: Neue Feature-Implementation
**Wenn der Entwickler sagt:**
- "Implementiere Feature X"
- "Füge Funktion Y hinzu"

**DANN führe ich AUTOMATISCH aus:**
1. Analysiere bestehenden Code
2. Erstelle Implementierungsplan mit Checkliste
3. Warne vor möglichen Breaking Changes
4. Warte auf Freigabe
5. Nach Implementation: Automatischer Pre-Commit Review

---

## ✅ Pre-Commit Code Review Checkliste

### 1. Home Assistant Compatibility ⚡
```
[ ] Keine deprecated APIs verwendet
    - async_timeout → asyncio.timeout ✓
    - homeassistant.exceptions → custom exceptions ✓
    - Alte OptionsFlow patterns → OptionsFlowWithReload ✓

[ ] Python 3.11+ kompatibel
    - Type hints verwenden
    - Moderne async/await patterns

[ ] Home Assistant 2024.1+ kompatibel
    - Config Entry API korrekt verwendet
    - Entity Registry patterns befolgt

[ ] Kein blocking I/O im Event Loop
    - Alle I/O mit async/await
    - Keine blocking imports
```

### 2. Integration Patterns 🏗️
```
[ ] CoordinatorEntity für coordinator-basierte Sensoren
    ✓ Inheritance: class MySensor(CoordinatorEntity, SensorEntity)
    ✓ __init__ ruft super().__init__(coordinator) auf
    ✓ should_poll NICHT manuell setzen (CoordinatorEntity macht das)
    ✓ Zugriff auf Daten via self.coordinator.data

[ ] Proper Exception Handling
    ✓ Custom Exceptions in config_flow.py definiert (InvalidAuth, CannotConnect)
    ✓ Nicht aus homeassistant.exceptions importieren
    ✓ UpdateFailed für Coordinator errors

[ ] Config Flow / Options Flow korrekt
    ✓ OptionsFlowWithReload ohne __init__ override
    ✓ config_entry automatisch verfügbar als self.config_entry
    ✓ async_get_options_flow gibt MarstekOptionsFlow() zurück (OHNE Parameter)

[ ] Entity Properties
    ✓ unique_id ist wirklich unique (device_id + sensor_key)
    ✓ device_info korrekt implementiert
    ✓ entity_category für diagnostic sensors (EntityCategory.DIAGNOSTIC)
```

### 3. Error Handling & Logging 📝
```
[ ] Try-except für alle API calls
    ✓ Spezifische Exceptions zuerst
    ✓ UpdateFailed für Coordinator
    ✓ Proper error messages

[ ] Logging korrekt verwendet
    ✓ DEBUG: Detaillierte API responses, Daten-Processing
    ✓ INFO: Wichtige Events (Login, Token refresh, Device count)
    ✓ WARNING: Recoverable errors, Retries
    ✓ ERROR: Echte Fehler, die Attention brauchen
    ✓ Keine sensiblen Daten (Passwords, Tokens) loggen
```

### 4. Code Quality 🎯
```
[ ] Type Hints vorhanden
    - Funktions-Parameter
    - Return Types
    - Class Attributes

[ ] Docstrings für public methods
    """Brief description.

    Args:
        param: Description

    Returns:
        Description

    Raises:
        ExceptionType: When it's raised
    """

[ ] Constants in const.py
    - Keine Magic Numbers
    - Keine Hardcoded Strings
    - DEFAULT_ prefix für Default-Werte

[ ] Code-Duplikation vermeiden
    - Gemeinsame Logik in Base-Classes
    - Helper-Functions für wiederholte Operationen
```

### 5. Breaking Changes Detection ⚠️
```
[ ] Entity IDs ändern sich NICHT
    - unique_id bleibt stabil
    - Namen können ändern, aber unique_id nicht

[ ] Config Entry Migration
    - Wenn data/options Schema ändert
    - async_migrate_entry implementieren

[ ] Backwards Compatibility
    - .get() mit Defaults für neue Felder
    - Graceful Handling von fehlenden Keys
```

### 6. Translations & Documentation 📚
```
[ ] Strings in translations/*.json
    - en.json (Englisch)
    - de.json (Deutsch)
    - Keine hardcoded UI-Strings im Code

[ ] README.md aktualisiert
    - Features korrekt beschrieben
    - Installation Guide aktuell
    - Troubleshooting wenn relevant

[ ] CHANGELOG.md entry
    - Version
    - Fixed/Added/Changed
    - Kurz und präzise
```

---

## 🔍 Code Review Output Format

Nach dem Review antworte ich IMMER in diesem Format:

```markdown
## 🤖 Pre-Commit Review

### Status: ✅ GO / ⚠️ NO-GO

### Checkliste:
✅ Home Assistant Compatibility
✅ Integration Patterns
⚠️ Error Handling (2 issues)
✅ Code Quality
✅ No Breaking Changes
✅ Documentation

### Issues gefunden:

#### ⚠️ Error Handling
1. **Fehlende Exception in coordinator.py:45**
   - `await api.get_devices()` ohne try-except
   - Fix: Wrap in try-except mit UpdateFailed

2. **Logging Level falsch in sensor.py:122**
   - `_LOGGER.error()` für normalen Flow
   - Fix: Ändern zu `_LOGGER.debug()`

### Empfehlung:
[✅ Bereit für Commit] / [❌ Bitte Issues fixen]

### Commit Message Vorschlag:
```
fix: Improve error handling in coordinator

- Add try-except for API calls
- Adjust logging levels for normal flow
```
```

---

## 🏗️ Development Workflow

### Phase 1: Planning
```
Entwickler: "Feature X implementieren"
AI:
  1. Analysiere bestehenden Code
  2. Identifiziere betroffene Dateien
  3. Erstelle Implementierungsplan
  4. Warne vor Breaking Changes
  5. Warte auf GO vom Entwickler
```

### Phase 2: Implementation
```
AI:
  1. Implementiere Code
  2. Führe SELBST-REVIEW durch (Checkliste)
  3. Zeige Code + Review-Ergebnis
Entwickler:
  1. Quick Check
  2. Feedback / Änderungswünsche
```

### Phase 3: Testing (by Entwickler)
```
1. Lokaler Test in Docker-HA
2. Test in echter HA-Umgebung
3. Bei Fehler: Zurück zu Phase 2
```

### Phase 4: Commit
```
Entwickler: "Ich will committen"
AI:
  1. Führe automatisch Pre-Commit Review durch
  2. Gebe GO/NO-GO
  3. Bei GO: Commit-Message-Vorschlag
  4. Bei NO-GO: Liste der Issues
```

---

## 🚨 Pattern-Guide: Häufige Fehler vermeiden

### ❌ FALSCH: should_poll mit SensorEntity
```python
class MySensor(SensorEntity):
    should_poll = False  # ❌ Sensor wird nicht aktualisiert!

    def __init__(self, coordinator):
        self.coordinator = coordinator
```

### ✅ RICHTIG: CoordinatorEntity verwenden
```python
class MySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, ...):
        super().__init__(coordinator)  # ✓ Registriert sich automatisch
```

---

### ❌ FALSCH: OptionsFlowWithReload mit __init__
```python
class MyOptionsFlow(OptionsFlowWithReload):
    def __init__(self, config_entry):  # ❌ TypeError!
        super().__init__(config_entry)
```

### ✅ RICHTIG: Kein __init__ override
```python
class MyOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        # self.config_entry ist automatisch verfügbar ✓
        options = self.config_entry.options
```

---

### ❌ FALSCH: Exceptions aus HA importieren
```python
from homeassistant.exceptions import InvalidAuth  # ❌ Removed in HA 2024+
```

### ✅ RICHTIG: Custom Exceptions definieren
```python
from homeassistant import exceptions

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""
```

---

### ❌ FALSCH: async_timeout verwenden
```python
import async_timeout  # ❌ Deprecated in Python 3.11+

async with async_timeout.timeout(10):
    await some_operation()
```

### ✅ RICHTIG: asyncio.timeout verwenden
```python
import asyncio  # ✓ Built-in, modern

async with asyncio.timeout(10):
    await some_operation()
```

---

## 📊 Home Assistant Best Practices

### Entity Naming
```python
# unique_id: Stabil, ändert sich NIE
self._attr_unique_id = f"{device_id}_{sensor_key}"

# name: Kann ändern, User-sichtbar
self._attr_name = f"{device_name} {sensor_label}"
```

### Device Classes & State Classes
```python
# Energie (kWh) - für Statistiken
SensorDeviceClass.ENERGY
SensorStateClass.TOTAL  # Nicht MEASUREMENT!

# Leistung (W) - Momentanwerte
SensorDeviceClass.POWER
SensorStateClass.MEASUREMENT

# Timestamps
SensorDeviceClass.TIMESTAMP
# Return: datetime object, nicht string!
return dt_util.now()
```

### Coordinator Pattern
```python
class MyCoordinator(DataUpdateCoordinator):
    async def _async_update_data(self):
        # Fetch data from API
        data = await self.api.get_data()
        return data  # Wird in self.data gespeichert

# Sensoren bekommen automatisch Updates:
class MySensor(CoordinatorEntity, SensorEntity):
    @property
    def native_value(self):
        # Liest aus self.coordinator.data
        return self.coordinator.data.get("value")
```

---

## 🎯 Version & Release

### Version Bumping
```
Patch (0.4.1 → 0.4.2): Bug fixes
Minor (0.4.0 → 0.5.0): New features, backwards compatible
Major (0.4.0 → 1.0.0): Breaking changes
```

### Commit Messages
```
Format: <type>: <description>

Types:
- fix: Bug fix
- feat: New feature
- chore: Maintenance (version bump, dependencies)
- docs: Documentation
- refactor: Code refactoring
- test: Tests

Beispiele:
fix: Correct sensor update mechanism
feat: Add support for battery capacity configuration
chore: Bump version to 0.4.3
```

---

## 🔄 Continuous Improvement

Nach jedem Release-Zyklus:
1. Was ist schief gelaufen?
2. Welche Fehler hätten wir fangen können?
3. Checkliste erweitern/anpassen
4. Diese Datei updaten

**Diese Datei ist ein lebendes Dokument!**

---

## 📝 Notizen für AI Agent

- Immer gegen diese Checkliste reviewen vor Commit
- Bei Unsicherheit: Lieber zu vorsichtig als zu nachlässig
- Breaking Changes IMMER explizit warnen
- Code-Qualität > Geschwindigkeit
- "Es funktioniert" ≠ "Es ist gut"

**Letztes Update:** 2026-01-04
**Version:** 1.0
