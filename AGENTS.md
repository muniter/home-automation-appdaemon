# AppDaemon Development

## Deploy & Logs

```bash
make deploy-appdaemon                                          # Deploy (auto-reloads)
ssh hassio 'ha addons logs a0d7b954_appdaemon --lines 100'     # View logs
ssh hassio 'ha addons restart a0d7b954_appdaemon'              # Restart addon
```

**Restart required for**: `appdaemon.yaml` changes. Code changes (including constants, imports) auto-reload.

**Note**: If auto-reload shows "Modification affects apps set()" as empty but changes aren't working, restart AppDaemon manually. The auto-reload tracking can sometimes get out of sync.

## Entity Commands

```bash
hass-cli state list 'binary_sensor.kitchen*'                   # Find entities by pattern
hass-cli state get binary_sensor.kitchen_motion                # Get state + last_changed
hass-cli service call light.turn_on --arguments entity_id=light.kitchen
```

## Debugging

1. Check logs for `initialized` message after deploy
2. No events firing? Verify entity IDs match HA (use `state list` to find correct names)
3. Check `last_changed` timestamp to see if sensor is updating
4. Query the HA database directly to see if events are firing:

```bash
# Recent events of a specific type
ssh hassio 'sqlite3 /config/home-assistant_v2.db "
  SELECT et.event_type, ed.shared_data, e.time_fired_ts 
  FROM events e 
  JOIN event_types et ON e.event_type_id = et.event_type_id 
  LEFT JOIN event_data ed ON e.data_id = ed.data_id 
  WHERE et.event_type = \"zha_event\" 
  ORDER BY e.time_fired_ts DESC LIMIT 10"'

# All recent events
ssh hassio 'sqlite3 /config/home-assistant_v2.db "
  SELECT et.event_type, ed.shared_data, e.time_fired_ts 
  FROM events e 
  JOIN event_types et ON e.event_type_id = et.event_type_id 
  LEFT JOIN event_data ed ON e.data_id = ed.data_id 
  ORDER BY e.time_fired_ts DESC LIMIT 20"'
```

This helps verify if events are reaching HA even when AppDaemon isn't receiving them.

## TTS (Text-to-Speech)

Use the BaseApp helper methods for TTS announcements:

```python
self.tts_first_floor("message")   # First floor Xiaomi gateway
self.tts_second_floor("message")  # Second floor Xiaomi gateway
self.tts_all("message")           # Both floors
```

**Important**: All TTS messages should be in **Spanish** (default language is `es-ES`).

## Restart Safety

AppDaemon can restart at any time (updates, crashes, server reboot). Automations must
survive restarts, especially long-running states like vacation mode (could be weeks).

**Two patterns:**

1. **Event-based (naturally safe)**: React to events and check current state.
   ```python
   # Good: checks state on each event, no init needed
   def on_door_opened(self, entity, attribute, old, new, **kwargs):
       if self.get_state("input_boolean.house_occupied") == "on":
           return  # Someone home, ignore
       self.send_alert("Door opened while away!")
   ```

2. **Long-running state (needs init check)**: If automation depends on a state that
   was set hours/days ago, you need BOTH a listener AND a startup check.
   ```python
   def initialize(self):
       # React to future changes
       self.listen_state(self._on_vacation_change, "input_boolean.vacation_mode")
       
       # BUT ALSO check current state on startup (vacation might have started days ago)
       if self.get_state("input_boolean.vacation_mode") == "on":
           self._start_vacation_behavior()
   ```

**Examples:**
- `security.py` - Event-based, checks `house_occupied` on each door/button event ✓
- `vacation_lights.py` - Listens for vacation mode changes + `run_at_sunset` (fires daily) + checks on startup ✓
- `left_on_notifier.py` - Listens for vacation mode changes + checks if ON at startup ✓

**Rule of thumb**: If a state could have been set before AppDaemon started and you
need to act on it, check it in `initialize()`.

## API Reference

The Hass API class provides many helper methods. Inspect the local file for available methods:

```
homeassistant/appdaemon/.venv/lib/python3.12/site-packages/appdaemon/plugins/hass/hassapi.py
```

Key methods include:
- `integration_entities(integration)` - Get entities for an integration (e.g., "tasmota")
- `device_id(entity_id)` - Get device ID for an entity
- `device_attr(device_id, attr)` - Get device attribute (e.g., "name", "name_by_user")
- `device_entities(device_id)` - Get entities for a device
- `area_entities(area_name)` - Get entities in an area
- `render_template(template)` - Render a Home Assistant template
