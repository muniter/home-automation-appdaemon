"""Low battery notification automation.

Monitors all battery sensors and alerts when any drop below threshold.

Behavior:
- Runs daily at 10:00 AM
- Checks all sensors with 'battery' in the entity ID
- Filters for sensors with numeric values (skips unavailable/unknown)
- Alerts Javier if any battery is below 20%
- Groups all low batteries into a single notification
"""

from common import BaseApp

LOW_BATTERY_THRESHOLD = 20


class LowBatteryNotifier(BaseApp):

    def initialize(self):
        # Run daily at 10:00 AM
        self.run_daily(self._check_batteries, "10:00:00")

        # Also run on startup (after a short delay to let entities load)
        self.run_in(self._check_batteries, 60)

        self.info("Low battery notifier initialized")

    def _check_batteries(self, kwargs):
        """Check all battery sensors and notify if any are low."""
        low_batteries: list[tuple[str, float]] = []

        # Get all entities and filter for battery sensors
        all_states = self.get_state()
        if not all_states:
            return

        for entity_id, state_info in all_states.items():
            # Only check sensors with 'battery' in the name
            if not entity_id.startswith("sensor.") or "battery" not in entity_id:
                continue

            # Skip non-level sensors (health, state, temperature, etc.)
            if not any(x in entity_id for x in ["_level", "_battery"]):
                if "_battery_" in entity_id:
                    continue

            state = state_info.get("state")
            if state in ("unavailable", "unknown", None):
                continue

            try:
                level = float(state)
            except (ValueError, TypeError):
                continue

            # Check if below threshold
            if level < LOW_BATTERY_THRESHOLD:
                # Get friendly name
                friendly_name = state_info.get("attributes", {}).get(
                    "friendly_name", entity_id
                )
                low_batteries.append((friendly_name, level))

        if not low_batteries:
            self.info("All batteries OK")
            return

        # Sort by level (lowest first)
        low_batteries.sort(key=lambda x: x[1])

        # Build notification message
        lines = [f"• {name}: {level:.0f}%" for name, level in low_batteries]
        message = "\n".join(lines)

        self.send_notification(
            targets=["javier"],
            message=message,
            title=f"Low Battery Alert ({len(low_batteries)} devices)",
        )
        self.info(f"Sent low battery alert for {len(low_batteries)} devices")
