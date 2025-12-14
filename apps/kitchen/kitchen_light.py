"""Kitchen light motion automation.

Two motion sensors with different trust levels:
- Entrance sensor: high confidence (you definitely walked into the kitchen)
- Kitchen sensor: can false-trigger from movement outside the kitchen

Turn ON:
- Entrance motion + house occupied → turn on
- Kitchen motion + house occupied + recent entrance motion (30s) → turn on

Turn OFF:
- 45s after all motion clears
- Sticky mode prevents auto-off

Sticky mode:
- Activates when light is turned on manually (not by motion)
- Deactivates when light is turned off
- While active, cancels any pending off timer
"""

from common import BaseApp

# How long entrance motion is considered "recent" for validating kitchen motion
ENTRANCE_LOOKBACK_SECONDS = 30


class KitchenMotionLight(BaseApp):

    KITCHEN_MOTION = "binary_sensor.kitchen_motion"
    ENTRANCE_MOTION = "binary_sensor.kitchen_entrance_motion"
    LIGHT_SWITCH = "switch.ls_kitchen"
    STICKY_MODE = "input_boolean.kitchen_light_sticky_on"
    HOUSE_OCCUPIED = "input_boolean.house_occupied"

    OFF_DELAY = 45  # seconds after motion clears

    def initialize(self):
        self.timer_handle = None
        self.motion_triggered_light = False

        self.listen_state(self.on_kitchen_motion, self.KITCHEN_MOTION)
        self.listen_state(self.on_entrance_motion, self.ENTRANCE_MOTION)
        self.listen_state(self.on_light_change, self.LIGHT_SWITCH)
        self.listen_state(self.on_sticky_change, self.STICKY_MODE)

        self.info("Kitchen motion light initialized")

    # --- Motion handlers ---

    def on_entrance_motion(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return
        if new == "on":
            self._cancel_timer()
            self._turn_on_if_home("entrance")
        elif new == "off":
            self._start_off_timer_if_clear()

    def on_kitchen_motion(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return
        if new == "on":
            self._cancel_timer()
            # Only trust kitchen sensor if entrance had recent motion
            if self._had_recent_entrance_motion():
                self._turn_on_if_home("kitchen")
            else:
                self.info("Kitchen motion ignored (no recent entrance motion)")
        elif new == "off":
            self._start_off_timer_if_clear()

    def _had_recent_entrance_motion(self) -> bool:
        """Check if entrance sensor is on or was recently on."""
        if self.get_state(self.ENTRANCE_MOTION) == "on":
            return True
        # Check last_changed to see if it was recently active
        last_changed = self.get_state(self.ENTRANCE_MOTION, attribute="last_changed")
        if last_changed and isinstance(last_changed, str):
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            changed = self.convert_utc(last_changed)
            seconds_ago = (now - changed).total_seconds()
            return seconds_ago < ENTRANCE_LOOKBACK_SECONDS
        return False

    def _turn_on_if_home(self, source: str):
        """Turn on light if house is occupied."""
        if self.get_state(self.HOUSE_OCCUPIED) != "on":
            self.info(f"Motion from {source} but house not occupied")
            return

        if self.get_state(self.LIGHT_SWITCH) == "off":
            self.motion_triggered_light = True
            self.call_service("switch/turn_on", entity_id=self.LIGHT_SWITCH)
            self.info(f"Motion from {source}, light ON")

    # --- Off timer ---

    def _start_off_timer_if_clear(self):
        """Start off timer if both sensors are clear and not sticky."""
        if self.get_state(self.STICKY_MODE) == "on":
            return

        kitchen = self.get_state(self.KITCHEN_MOTION)
        entrance = self.get_state(self.ENTRANCE_MOTION)

        if kitchen in ["off", "unavailable"] and entrance in ["off", "unavailable"]:
            self._cancel_timer()
            self.timer_handle = self.run_in(self._turn_off_light, self.OFF_DELAY)
            self.info(f"All motion clear, {self.OFF_DELAY}s timer started")

    def _turn_off_light(self, kwargs):
        """Turn off light after timer expires."""
        self.timer_handle = None

        if self.get_state(self.STICKY_MODE) == "on":
            self.info("Timer expired but sticky mode ON")
            return

        if self.get_state(self.KITCHEN_MOTION) == "on" or self.get_state(self.ENTRANCE_MOTION) == "on":
            self.info("Timer expired but motion detected")
            return

        if self.get_state(self.LIGHT_SWITCH) == "on":
            self.call_service("switch/turn_off", entity_id=self.LIGHT_SWITCH)
            self.info("Timer expired, light OFF")

    def _cancel_timer(self):
        if self.timer_handle:
            self.cancel_timer(self.timer_handle)
            self.timer_handle = None

    # --- Sticky mode ---

    def on_light_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return

        if new == "on" and not self.motion_triggered_light:
            # Manual turn on → enable sticky
            self.call_service("input_boolean/turn_on", entity_id=self.STICKY_MODE)
            self.info("Manual light ON, sticky enabled")
        elif new == "off":
            # Any turn off → disable sticky
            self.call_service("input_boolean/turn_off", entity_id=self.STICKY_MODE)
            self.motion_triggered_light = False
            self.info("Light OFF, sticky disabled")

    def on_sticky_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return

        if new == "on":
            self._cancel_timer()
            if self.get_state(self.LIGHT_SWITCH) == "off":
                self.motion_triggered_light = True
                self.call_service("switch/turn_on", entity_id=self.LIGHT_SWITCH)
                self.info("Sticky ON, turning light ON")
