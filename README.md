# Home Automation with AppDaemon

Python-based home automations for [Home Assistant](https://www.home-assistant.io/) using [AppDaemon](https://appdaemon.readthedocs.io/).

## Why AppDaemon?

After years of struggling with YAML automations and Node-RED flows, I switched to AppDaemon. The key insight: **if you can convert a problem into a code generation problem, LLMs can help you build it**.

AppDaemon is pure Python, which means:
- LLMs (like Claude) can generate idiomatic automations from natural language
- Full IDE support with type hints
- Easy to test, refactor, and version control
- No JSON/YAML wrestling

Read the full blog post: [Home Automation Finally Clicked — Thanks to LLMs](https://javierlopez.dev/blog/home-automation-with-llms/)

## Structure

```
apps/
├── common.py           # Base class with notification/TTS helpers
├── notify.py           # Smart notification routing
├── house/              # House-wide automations
│   ├── occupancy.py    # Track if anyone is home
│   ├── security.py     # Alerts when doors open while away
│   ├── welcome_home.py # TTS greetings on arrival
│   ├── outside_lights.py
│   ├── vacation_lights.py
│   ├── vacation_mode.py
│   ├── left_on_notifier.py
│   ├── low_battery_notifier.py
│   ├── arrival_notifier.py
│   └── buttons.py
├── kitchen/
│   └── kitchen_light.py
└── main_room/
    └── closet_light.py
```

## Key Patterns

### Base Class with Helpers

All apps inherit from `BaseApp` which provides:
- `send_notification(targets, message, title)` - Smart routing to phones/tablets/TV
- `tts_first_floor(message)` / `tts_all(message)` - Text-to-speech announcements
- `info()` / `debug()` - Prefixed logging

### Smart Notification Routing

Instead of hardcoding notification targets:

```python
# Old way - brittle
self.call_service("notify/mobile_app_javier_phone", message="Hello")

# New way - context-aware
self.send_notification(
    targets=["home"],  # Everyone home + active devices
    message="Front door opened",
)
```

The router (`notify.py`) checks device states and sends to the right places.

### Restart-Safe Design

AppDaemon can restart anytime. Long-running states need both a listener AND a startup check:

```python
def initialize(self):
    # React to future changes
    self.listen_state(self._on_vacation_change, "input_boolean.vacation_mode")
    
    # Check current state on startup (vacation might have started days ago)
    if self.get_state("input_boolean.vacation_mode") == "on":
        self._start_vacation_behavior()
```

## Deployment

Apps are deployed via rsync (AppDaemon auto-reloads):

```bash
rsync -av --delete \
  --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' \
  apps/ hassio:/addon_configs/a0d7b954_appdaemon/apps/
```

## Setup

1. Install the [AppDaemon add-on](https://github.com/hassio-addons/addon-appdaemon) in Home Assistant
2. Clone this repo
3. Update `appdaemon.yaml` with your coordinates and timezone
4. Customize entity IDs in the apps to match your setup
5. Deploy with rsync

## Development

```bash
# Create virtualenv for IDE support
uv sync

# Type checking
uv run pyright
```

See `AGENTS.md` for debugging tips and API reference.

## License

MIT

