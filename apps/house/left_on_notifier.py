"""Notify when leaving with things still on.

When house_occupied turns OFF:
1. Turn off outside lights immediately
2. Wait 2 minutes for other things to turn off
3. If anything still on, send actionable notification with "Turn everything off" button

Vacation mode:
    When vacation mode is ON, we expect lights to be on for fake presence.
    Instead of alerting immediately, we wait 2 hours. This allows vacation
    lights to cycle (they turn off/on periodically to stay under this threshold).
    If something is on for 2+ hours continuously, it might be a real issue.

Handles the mobile_app notification action to turn everything off.
"""

from common import BaseApp

# Normal mode: wait 2 minutes after leaving before checking
WAIT_MINUTES = 2

# Vacation mode: wait 2 hours before alerting (vacation lights cycle under this)
VACATION_WAIT_HOURS = 2


class LeftOnNotifier(BaseApp):

    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    VACATION_MODE = "input_boolean.vacation_mode"
    ALL_DEVICES_GROUP = "group.all_switch_and_devices"
    OUTSIDE_GROUP = "group.outside"

    def initialize(self):
        self.vacation_check_timer = None

        self.listen_state(
            self.on_house_unoccupied,
            self.HOUSE_OCCUPIED,
            new="off"
        )

        # In vacation mode, periodically check for things left on too long
        self.listen_state(
            self._on_vacation_mode_change,
            self.VACATION_MODE,
        )

        # Listen for the actionable notification response
        self.listen_event(self.on_action_triggered, event="mobile_app_notification_action")

        # If vacation mode is already on at startup, start periodic checking
        if self.get_state(self.VACATION_MODE) == "on":
            self._start_vacation_check()

        self.info("Left on notifier initialized")

    def on_house_unoccupied(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """House became unoccupied - turn off outside lights, then check rest."""
        if old == new:
            return

        # In vacation mode, skip normal checking (vacation_check handles it)
        if self.get_state(self.VACATION_MODE) == "on":
            self.info("Vacation mode - skipping normal left-on check")
            return

        # Turn off outside lights immediately
        if self.get_state(self.OUTSIDE_GROUP) == "on":
            self.call_service("homeassistant/turn_off", entity_id=self.OUTSIDE_GROUP)
            self.info("Turned off outside lights")

        # Wait 2 minutes then check if anything still on
        self.run_in(self._check_and_notify, WAIT_MINUTES * 60)
        self.info(f"Will check for things left on in {WAIT_MINUTES} minutes")

    def _check_and_notify(self, kwargs):
        """Check if anything still on and send notification."""
        # Re-check house is still unoccupied
        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            self.info("House occupied again, skipping notification")
            return

        on_entities = self._get_on_entities()

        if not on_entities:
            self.info("Everything is off")
            return

        # Build message with entity names
        names = [self._friendly_name(e) for e in on_entities]
        time_str = self.datetime().strftime("%H:%M")
        message = f"At {time_str} House is empty, and this are on: {', '.join(names)}"

        # Send actionable notification to both
        self.send_notification(
            targets=["both"],
            message=message,
            title="Something is turned ON",
            data={
                "tag": "house_turned_on",
                "clickAction": "/lovelace/main",
                "actions": [
                    {"action": "turn_everything_off", "title": "Turn everything off"}
                ],
                "priority": "high"
            }
        )
        self.info(f"Sent notification: {message}")

    def on_action_triggered(self, event_type: str, data: dict, **kwargs):
        """Handle notification action button press."""
        action = data.get("action")

        if action == "turn_everything_off":
            self.call_service("homeassistant/turn_off", entity_id=self.ALL_DEVICES_GROUP)
            self.info("Turned everything off via notification action")

    def _get_on_entities(self) -> list[str]:
        """Get list of entities in group that are on."""
        group_state = self.get_state(self.ALL_DEVICES_GROUP, attribute="all")
        if not group_state:
            return []

        entity_ids = group_state.get("attributes", {}).get("entity_id", [])
        on_entities = []

        for entity_id in entity_ids:
            state = self.get_state(entity_id)
            if state not in ["off", "unknown", "unavailable"]:
                on_entities.append(entity_id)

        return on_entities

    def _friendly_name(self, entity_id: str) -> str:
        """Get friendly name for an entity."""
        state = self.get_state(entity_id, attribute="all")
        if state and "attributes" in state:
            return state["attributes"].get("friendly_name", entity_id)
        return entity_id

    # --- Vacation mode handling ---

    def _on_vacation_mode_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Vacation mode changed - start or stop periodic checking."""
        if old == new:
            return

        if new == "on":
            # Start periodic checking every 2 hours
            self._start_vacation_check()
            self.info("Vacation mode ON - switched to 2-hour check interval")
        else:
            # Stop periodic checking
            self._cancel_vacation_check()
            self.info("Vacation mode OFF - back to normal mode")

    def _start_vacation_check(self):
        """Start periodic check for things left on during vacation."""
        self._cancel_vacation_check()
        self.vacation_check_timer = self.run_every(
            self._vacation_check,
            f"now+{VACATION_WAIT_HOURS}:00:00",
            VACATION_WAIT_HOURS * 60 * 60,
        )

    def _cancel_vacation_check(self):
        """Cancel vacation mode periodic check."""
        if self.vacation_check_timer:
            self.cancel_timer(self.vacation_check_timer)
            self.vacation_check_timer = None

    def _vacation_check(self, kwargs):
        """Check if anything has been on too long during vacation."""
        # Only check if still in vacation mode and house unoccupied
        if self.get_state(self.VACATION_MODE) != "on":
            return
        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            return

        on_entities = self._get_on_entities()

        if not on_entities:
            return

        # Build message
        names = [self._friendly_name(e) for e in on_entities]
        message = f"Vacation mode: these have been on for a while: {', '.join(names)}"

        self.send_notification(
            targets=["javier"],
            message=message,
            title="Vacation Alert",
            data={
                "tag": "vacation_left_on",
                "actions": [
                    {"action": "turn_everything_off", "title": "Turn everything off"}
                ],
            }
        )
        self.info(f"Vacation alert: {message}")
