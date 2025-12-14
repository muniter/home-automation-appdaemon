"""Main room closet light automation."""

from common import BaseApp


class ClosetMotionLight(BaseApp):
    """Turn closet light on/off based on motion detection.

    When motion is detected and house is occupied:
    - Turn on the closet light

    When motion clears:
    - Start a 90-second timer
    - After timeout, turn off the light if it's still on

    Continuous motion resets the timer.
    """

    MOTION_SENSOR = "binary_sensor.closet_motion_sensor_occupancy"
    LIGHT_SWITCH = "switch.ls_main_closet"
    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    OFF_DELAY_SECONDS = 90

    def initialize(self):
        self.timer_handle = None
        self.listen_state(self.on_motion_change, self.MOTION_SENSOR)
        self.info("Closet motion light initialized")

    def on_motion_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return

        if new == "on":
            self._on_motion_detected()
        elif new == "off":
            self._on_motion_cleared()

    def _on_motion_detected(self):
        """Handle motion detected event."""
        # Cancel any pending off timer
        self._cancel_timer()

        # Only turn on light if house is occupied
        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            self.call_service("switch/turn_on", entity_id=self.LIGHT_SWITCH)
            self.info("Motion detected, turning on closet light")
        else:
            self.info("Motion detected but house not occupied, ignoring")

    def _on_motion_cleared(self):
        """Handle motion cleared event - start timer to turn off light."""
        self._cancel_timer()
        self.timer_handle = self.run_in(self._turn_off_light, self.OFF_DELAY_SECONDS)
        self.info(f"Motion cleared, starting {self.OFF_DELAY_SECONDS}s timer")

    def _turn_off_light(self, kwargs):
        """Turn off light if it's currently on."""
        self.timer_handle = None

        if self.get_state(self.LIGHT_SWITCH) == "on":
            self.call_service("switch/turn_off", entity_id=self.LIGHT_SWITCH)
            self.info("Timer expired, turning off closet light")
        else:
            self.info("Timer expired but light already off")

    def _cancel_timer(self):
        """Cancel the pending off timer if active."""
        if self.timer_handle is not None:
            self.cancel_timer(self.timer_handle)
            self.timer_handle = None
