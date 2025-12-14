"""House occupancy automation.

Tracks whether the house is occupied based on person presence.

Turn ON (immediately):
- Javier or Andy arrives home

Turn OFF (with 5 min delay):
- Both Javier and Andy are away
- Guest mode is OFF
- Wait 5 minutes (buffer for presence detection glitches)
- Then turn OFF house_occupied

Location sync:
- When one person arrives or leaves, request location update from the other
- They often travel together, so this helps sync presence faster

Guest mode:
- When ON, prevents house_occupied from turning off
- Use for guests without tracked presence
"""

from common import BaseApp

# Delay before turning off house_occupied after everyone leaves
# Buffer for presence detection glitches (e.g., UniFi briefly reporting away)
DEPARTURE_DELAY_MINUTES = 5


class HouseOccupancy(BaseApp):

    JAVIER = "person.javier"
    ANDY = "person.andy"
    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    GUEST_MODE = "input_boolean.guest_mode"

    def initialize(self):
        self.departure_timer = None

        self.listen_state(self.on_javier_presence, self.JAVIER)
        self.listen_state(self.on_andy_presence, self.ANDY)

        self.info("House occupancy initialized")

    def on_javier_presence(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return
        if new == "home":
            self._on_person_arrived("Javier")
        else:
            self._on_person_left("Javier")

    def on_andy_presence(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        if old == new:
            return
        if new == "home":
            self._on_person_arrived("Andy")
        else:
            self._on_person_left("Andy")

    def _request_other_location(self, name: str):
        """Request location update from the other person's phone."""
        if name == "Javier":
            self.call_service("notify/mobile_app_andy_phone", message="request_location_update")
            self.info("Requested location update from Andy's phone")
        else:
            self.call_service("notify/mobile_app_javier_phone", message="request_location_update")
            self.info("Requested location update from Javier's phone")

    def _on_person_arrived(self, name: str):
        """Someone arrived home - turn on house_occupied and ping the other phone."""
        self._cancel_departure()

        # Request location update from the other person (they often arrive together)
        self._request_other_location(name)

        if self.get_state(self.HOUSE_OCCUPIED) == "off":
            self.call_service("input_boolean/turn_on", entity_id=self.HOUSE_OCCUPIED)
            self.info(f"{name} arrived, house occupied ON")
        else:
            self.info(f"{name} arrived, house already occupied")

    def _on_person_left(self, name: str):
        """Someone left - check if house should become unoccupied."""
        # Request location update from the other person (they often leave together)
        self._request_other_location(name)

        javier_home = self.get_state(self.JAVIER) == "home"
        andy_home = self.get_state(self.ANDY) == "home"

        if javier_home or andy_home:
            self.info(f"{name} left, but someone still home")
            return

        if self.get_state(self.GUEST_MODE) == "on":
            self.info(f"{name} left, but guest mode ON")
            return

        # Everyone left - start departure timer
        self._cancel_departure()
        self.departure_timer = self.run_in(
            self._on_departure_timer,
            DEPARTURE_DELAY_MINUTES * 60
        )
        self.info(f"{name} left, everyone away - {DEPARTURE_DELAY_MINUTES}min timer started")

    def _on_departure_timer(self, kwargs):
        """Departure timer expired - turn off house_occupied."""
        self.departure_timer = None

        # Re-check conditions (someone may have returned)
        javier_home = self.get_state(self.JAVIER) == "home"
        andy_home = self.get_state(self.ANDY) == "home"

        if javier_home or andy_home:
            self.info("Timer expired but someone returned home")
            return

        if self.get_state(self.GUEST_MODE) == "on":
            self.info("Timer expired but guest mode ON")
            return

        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            self.call_service("input_boolean/turn_off", entity_id=self.HOUSE_OCCUPIED)
            self.info("House occupied OFF")

    def _cancel_departure(self):
        """Cancel pending departure timer."""
        if self.departure_timer:
            self.cancel_timer(self.departure_timer)
            self.departure_timer = None
