"""Outside lights automation.

Manages outside lights based on doors and sunset.
Only runs when house is occupied (security handles unoccupied case).

Triggers:
- Sun goes down while house occupied → turn on stairs light
- Front door opens after sunset → turn on front door light
- Back gate opens after sunset → turn on outside lights
- Sun goes down while front door open → turn on front door light
- Sun goes down while back gate open → turn on outside lights
"""

from common import BaseApp


class OutsideLights(BaseApp):

    FRONT_DOOR = "binary_sensor.front_door_state"
    BACK_GATE = "binary_sensor.back_gate_state"
    FRONT_DOOR_LIGHT = "switch.ls_front_door"
    OUTSIDE_LIGHTS = "group.outside"
    STAIRS_LIGHT = "light.stairs"
    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    SUN = "sun.sun"

    def initialize(self):
        self.front_door_light_timer = None

        # Front door open/close
        self.listen_state(self.on_front_door_changed, self.FRONT_DOOR)

        # Back gate opens
        self.listen_state(self.on_back_gate_opened, self.BACK_GATE, new="on")

        # When sun goes down
        self.listen_state(self.on_sun_down, self.SUN, new="below_horizon")

        self.info("Outside lights initialized")

    def on_front_door_changed(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Front door state changed - control front door light."""
        if old == new:
            return

        if self.get_state(self.HOUSE_OCCUPIED) != "on":
            return

        if new == "on" and self.sun_down():
            # Door opened after sunset - turn on light, cancel any pending off timer
            self._cancel_front_door_light_timer()
            self.call_service("homeassistant/turn_on", entity_id=self.FRONT_DOOR_LIGHT)
            self.info("Front door opened after sunset - turned on front door light")
        elif new == "off":
            # Door closed - start 5 min timer to turn off light if it's on
            if self.get_state(self.FRONT_DOOR_LIGHT) == "on":
                self._cancel_front_door_light_timer()
                self.front_door_light_timer = self.run_in(self._turn_off_front_door_light, 5 * 60)
                self.info("Front door closed - will turn off light in 5 minutes")

    def _turn_off_front_door_light(self, kwargs):
        """Turn off front door light after timer expires."""
        self.front_door_light_timer = None
        self.call_service("homeassistant/turn_off", entity_id=self.FRONT_DOOR_LIGHT)
        self.info("Timer expired - turned off front door light")

    def _cancel_front_door_light_timer(self):
        """Cancel pending front door light timer."""
        if self.front_door_light_timer:
            self.cancel_timer(self.front_door_light_timer)
            self.front_door_light_timer = None

    def on_back_gate_opened(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Back gate opened - turn on outside lights if dark and occupied."""
        if old == new:
            return

        if self.get_state(self.HOUSE_OCCUPIED) != "on":
            return

        if self.sun_down():
            self.call_service("homeassistant/turn_on", entity_id=self.OUTSIDE_LIGHTS)
            self.info("Back gate opened after sunset - turned on outside lights")

    def on_sun_down(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Sun went down - turn on lights if occupied."""
        if old == new:
            return

        if self.get_state(self.HOUSE_OCCUPIED) != "on":
            return

        # Always turn on stairs light at sunset
        self.call_service("homeassistant/turn_on", entity_id=self.STAIRS_LIGHT)
        self.info("Sun went down - turned on stairs light")

        # Turn on front door light if front door is open
        if self.get_state(self.FRONT_DOOR) == "on":
            self.call_service("homeassistant/turn_on", entity_id=self.FRONT_DOOR_LIGHT)
            self.info("Sun went down with front door open - turned on front door light")

        # Turn on outside lights if back gate is open
        if self.get_state(self.BACK_GATE) == "on":
            self.call_service("homeassistant/turn_on", entity_id=self.OUTSIDE_LIGHTS)
            self.info("Sun went down with back gate open - turned on outside lights")
