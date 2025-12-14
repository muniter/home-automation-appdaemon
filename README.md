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

### Home Assistant

AppDaemon runs as a [Home Assistant add-on](https://appdaemon.readthedocs.io/en/latest/INSTALL.html). To install:

1. In Home Assistant, go to **Settings** → **Add-ons** → **Add-on Store**
2. Search for "AppDaemon" and install it
3. Configure the add-on with your coordinates and timezone
4. Start the add-on

The apps in this repo get deployed to the add-on via rsync (see Deployment above).

### Local Development

The `pyproject.toml` and `uv sync` setup is for **local development only** — AppDaemon itself runs inside the Home Assistant add-on, not on your development machine.

Why bother with a local virtualenv? When using LLM coding tools like [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or similar, having AppDaemon installed locally gives you:

- **Type checking** — Pyright catches errors before deployment
- **IDE autocomplete** — Your editor knows about `self.listen_state()`, `self.call_service()`, etc.
- **Linting** — The language server can validate your code

Without this, your LLM is flying blind — it can still generate code, but you won't catch typos or API misuse until runtime.

```bash
# One-time setup for IDE support
uv sync

# Type check before deploying
uv run pyright
```

### Teaching the Agent About Your Setup

One powerful trick: give your LLM access to the [Home Assistant CLI](https://www.home-assistant.io/common-tasks/os/#home-assistant-via-the-command-line) (`hass-cli`). The agent can then query your actual Home Assistant instance to:

- **Discover entities** — `hass-cli state list 'binary_sensor.kitchen*'`
- **Check current state** — `hass-cli state get binary_sensor.front_door`
- **Test services** — `hass-cli service call light.turn_on --arguments entity_id=light.kitchen`

This lets the LLM propose automations based on what's *actually* in your setup, not just guessing entity names. You describe what you want ("notify me when the garage door is left open"), and the agent can find the right sensors, check their current state, and write code that uses the correct entity IDs.

See `AGENTS.md` for more CLI examples and debugging tips.

## License

MIT

