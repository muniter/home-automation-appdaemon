"""Welcome home automation.

Two main functions:

1. Occupancy Change Handling:
   - When house becomes occupied: turn on lights (if after sunset), send notification
   - When house becomes unoccupied: send notification

2. Welcome TTS on Entry:
   - Listens to front door and back gate opening
   - Plays welcome message on first floor speaker when someone arrives

TTS Logic:
   We trigger TTS on door/gate open (not on occupancy change) because presence
   detection (GPS/WiFi) might fire BEFORE the person physically enters. By
   listening to the door, we ensure they're actually walking in.

   Three scenarios:
   
   a) Door opens, house NOT yet occupied (presence detection slow):
      → "Bienvenidos a casa, detectando presencia"
      Softer message acknowledging we're still figuring out who's home.
   
   b) Door opens, house JUST became occupied (within 5 min):
      → "Bienvenidos a casa"
      Normal welcome. The 5-min window accounts for parking, walking up, etc.
   
   c) Door opens, house was ALREADY occupied:
      → No TTS
      Someone's already home, no need to announce arrivals.
"""

from common import BaseApp

# Time window to consider "just became occupied" (accounts for parking, walking, etc.)
RECENT_OCCUPIED_SECONDS = 300

# Delay before playing TTS so person is inside
TTS_DELAY_SECONDS = 5


class WelcomeHome(BaseApp):

    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    LIVING_ROOM_LIGHTS = "group.living_room_lights_and_switches"
    OUTSIDE_LIGHTS = "group.outside"
    FRONT_DOOR = "binary_sensor.front_door_state"
    BACK_GATE = "binary_sensor.back_gate_state"
    JAVIER = "person.javier"
    ANDY = "person.andy"

    def initialize(self):
        # Track who was home before door opened
        self.presence_before_door: dict[str, bool] = {}

        self.listen_state(self.on_occupied_changed, self.HOUSE_OCCUPIED)
        self.listen_state(self.on_entry_point, self.FRONT_DOOR, new="on")
        self.listen_state(self.on_entry_point, self.BACK_GATE, new="on")
        self.info("Welcome home initialized")

    def on_occupied_changed(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """House occupancy changed - handle lights and notifications."""
        if old == new:
            return

        time_str = self.datetime().strftime("%-I:%M %p")

        if new == "on":
            self.info("House became occupied")

            # Turn on lights if after sunset
            if self.sun_down():
                self.call_service("homeassistant/turn_on", entity_id=self.LIVING_ROOM_LIGHTS)
                self.call_service("homeassistant/turn_on", entity_id=self.OUTSIDE_LIGHTS)
                self.info("After sunset - turned on living room and outside lights")

            self.send_notification(
                targets=["both"],
                message=f"House is now occupied at {time_str}",
                title="House Status",
            )

        elif new == "off":
            self.info("House became unoccupied")
            self.send_notification(
                targets=["both"],
                message=f"House is now unoccupied at {time_str}",
                title="House Status",
            )

    def on_entry_point(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Entry point opened (front door or back gate) - check if we should play welcome TTS."""
        # Snapshot current presence before it might change
        self.presence_before_door = {
            "javier": self.get_state(self.JAVIER) == "home",
            "andy": self.get_state(self.ANDY) == "home",
        }

        # Schedule TTS check after delay (person needs to get inside)
        self.run_in(self._check_and_play_welcome, TTS_DELAY_SECONDS)
        self.info(f"Door opened, presence snapshot: {self.presence_before_door}")

    def _check_and_play_welcome(self, kwargs):
        """Check arrival status and play welcome TTS only for first arrival."""
        house_occupied = self.get_state(self.HOUSE_OCCUPIED) == "on"

        if not house_occupied:
            # House not yet occupied - presence detection is slow
            # Play softer welcome while we figure things out
            self.tts_first_floor("Bienvenidos a casa, detectando presencia")
            self.info("Welcome TTS: house not yet occupied, detecting presence")
            return

        # Check if house_occupied recently turned on
        occupied_state = self.get_state(self.HOUSE_OCCUPIED, attribute="all") or {}
        last_changed = occupied_state.get("last_changed")

        house_just_occupied = False
        if last_changed:
            # Parse last_changed and check if within threshold
            from datetime import datetime, timezone

            changed_dt = datetime.fromisoformat(last_changed.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            seconds_ago = (now - changed_dt).total_seconds()
            house_just_occupied = seconds_ago < RECENT_OCCUPIED_SECONDS
            self.info(f"House occupied changed {seconds_ago:.0f}s ago")

        if house_just_occupied:
            # First arrival - welcome home
            self.tts_first_floor("Bienvenidos a casa")
            self.info("Welcome TTS: first arrival")
        else:
            # House was already occupied - no TTS needed
            self.info("House already occupied, skipping TTS")
