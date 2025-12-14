"""Button automations.

Handles physical button presses from various integrations:
- ZHA buttons (first floor): listen to zha_event
- Xiaomi Aqara buttons: listen to xiaomi_aqara.click
- Zigbee2MQTT buttons: listen to sensor state changes

Downstairs Button (ZHA):
- Single click: Turn on living room TV and standing fan
- Double click: Turn off first floor (except guest room if guest mode enabled)
- Furious click: Turn off whole house + TTS announcement
"""

from common import BaseApp


class Buttons(BaseApp):

    # Downstairs button (ZHA)
    DOWNSTAIRS_BUTTON_DEVICE_ID = "750cb4eea61645d4b9addd17baf5c44a"

    # Groups
    FIRST_FLOOR = "group.first_floor"
    FIRST_FLOOR_NO_GUEST = "group.first_floor_no_guest_room"
    WHOLE_HOUSE = "group.all_switch_and_devices"
    GUEST_MODE = "input_boolean.guest_mode"

    # Living room devices
    LIVING_ROOM_TV = "media_player.living_room_tv"
    LIVING_ROOM_STANDING_FAN = "switch.tasmota"

    def initialize(self):
        # Listen for ZHA button events
        self.listen_event(self.on_zha_event, event="zha_event")

        self.info("Buttons initialized")

    def on_zha_event(self, event_type: str, data: dict, **kwargs):
        """Handle ZHA button events."""
        device_id = data.get("device_id")
        command = data.get("command", "")
        args = data.get("args", {})

        if device_id == self.DOWNSTAIRS_BUTTON_DEVICE_ID:
            self._handle_downstairs_button(command, args)

    def _handle_downstairs_button(self, command: str, args: dict):
        """Handle downstairs button presses."""
        if command != "click":
            return

        click_type = args.get("click_type")

        if click_type == "single":
            self._toggle_living_room_tv_and_fan()
        elif click_type == "double":
            self._turn_off_first_floor()
        elif click_type == "furious":
            self._turn_off_whole_house()

    def _toggle_living_room_tv_and_fan(self):
        """Turn on living room TV and standing fan."""
        self.call_service("media_player/turn_on", entity_id=self.LIVING_ROOM_TV)
        self.call_service("switch/turn_on", entity_id=self.LIVING_ROOM_STANDING_FAN)
        self.info("Single click - turned on living room TV and standing fan")

    def _turn_off_first_floor(self):
        """Turn off first floor, respecting guest mode."""
        if self.get_state(self.GUEST_MODE) == "on":
            self.call_service("homeassistant/turn_off", entity_id=self.FIRST_FLOOR_NO_GUEST)
            self.info("Double click - turned off first floor (except guest room)")
        else:
            self.call_service("homeassistant/turn_off", entity_id=self.FIRST_FLOOR)
            self.info("Double click - turned off first floor")

    def _turn_off_whole_house(self):
        """Turn off the whole house."""
        self.call_service("homeassistant/turn_off", entity_id=self.WHOLE_HOUSE)
        self.tts_first_floor("Toda la casa apagada")
        self.info("Furious click - turned off whole house")
