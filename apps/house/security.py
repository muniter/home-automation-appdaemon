"""House security automation.

Monitors entry points and alerts when unexpected access is detected.

Entry point monitoring:
- When front door or back gate opens while house is unoccupied
- Request location updates from phones to speed up presence detection
- Turn on lights if after sunset
- Wait 30 seconds for someone to arrive
- If no one arrives, send security alert

Switch button monitoring:
- When a Tasmota switch button is physically pressed while house is unoccupied
- Send immediate security alert with device name
"""

from common import BaseApp

# Time to wait for occupancy after entry point opens while unoccupied
ENTRY_ALERT_SECONDS = 30


class HouseSecurity(BaseApp):

    HOUSE_OCCUPIED = "input_boolean.house_occupied"
    LIVING_ROOM_LIGHTS = "group.living_room_lights_and_switches"
    OUTSIDE_LIGHTS = "group.outside"

    # Entry points
    FRONT_DOOR = "binary_sensor.front_door_state"
    BACK_GATE = "binary_sensor.back_gate_state"

    ENTRY_POINTS = {
        FRONT_DOOR: "Front door",
        BACK_GATE: "Back gate",
    }

    def initialize(self):
        self.entry_alert_timer = None

        # Entry point monitoring
        for entity in self.ENTRY_POINTS:
            self.listen_state(self.on_entry_opened, entity, new="on")

        # Tasmota button press monitoring
        self.listen_event(self.on_tasmota_event, event="tasmota_event")
        self._build_mac_to_name_cache()

        self.info("House security initialized")

    def on_entry_opened(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Entry point opened - check if house is unoccupied and respond."""
        if old == new:
            return

        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            return

        entry_name = self.ENTRY_POINTS.get(entity, "Unknown entry")
        self.info(f"{entry_name} opened while house unoccupied")

        # Request location updates from phones to speed up presence detection
        self.call_service("notify/mobile_app_javier_phone", message="request_location_update")
        self.call_service("notify/mobile_app_andy_phone", message="request_location_update")
        self.info("Requested location updates from phones")

        # Turn on lights if after sunset
        if self.sun_down():
            self.call_service("homeassistant/turn_on", entity_id=self.LIVING_ROOM_LIGHTS)
            self.call_service("homeassistant/turn_on", entity_id=self.OUTSIDE_LIGHTS)
            self.info("After sunset - turned on lights")

        # Start timer to alert if no occupancy change
        self._cancel_entry_alert()
        self.entry_alert_timer = self.run_in(
            self._on_entry_alert_timer,
            ENTRY_ALERT_SECONDS,
            entry_name=entry_name,
        )

    def _on_entry_alert_timer(self, kwargs):
        """Entry alert timer expired - no one arrived, send alert."""
        self.entry_alert_timer = None

        # Re-check if house is still unoccupied
        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            return

        entry_name = kwargs.get("entry_name", "Entry point")
        time_str = self.datetime().strftime("%-I:%M %p")
        self.send_notification(
            targets=["both"],
            message=f"{entry_name} opened at {time_str} but no one arrived!",
            title="Security Alert",
            data={"priority": "high"},
        )
        self.info(f"Alert: {entry_name} opened but no occupancy change detected")

    def _cancel_entry_alert(self):
        """Cancel pending entry alert timer."""
        if self.entry_alert_timer:
            self.cancel_timer(self.entry_alert_timer)
            self.entry_alert_timer = None

    # --- Tasmota button press monitoring ---

    def _build_mac_to_name_cache(self):
        """Build MAC to device name cache from Tasmota switch entities."""
        self.mac_to_name: dict[str, str] = {}

        try:
            # Get all switch entities and check for Tasmota devices
            switches = self.get_state("switch")
            if not switches:
                return

            for entity_id in switches:
                try:
                    device_id = self.device_id(entity_id)
                    if not device_id:
                        continue

                    # Get device connections (contains MAC)
                    connections = self.device_attr(device_id, "connections")
                    if not connections:
                        continue

                    # Find MAC in connections
                    for conn in connections:
                        if conn[0] == "mac":
                            mac = conn[1].upper().replace(":", "")
                            name = self.device_attr(device_id, "name_by_user")
                            if not name:
                                name = self.device_attr(device_id, "name")
                            if name:
                                self.mac_to_name[mac] = name
                            break
                except Exception:
                    pass

            self.info(f"Built MAC cache with {len(self.mac_to_name)} devices")
        except Exception as e:
            self.info(f"Failed to build MAC cache: {e}")

    def _get_device_name_by_mac(self, mac: str) -> str:
        """Look up device name by MAC address."""
        return self.mac_to_name.get(mac.upper(), "A light switch")

    def on_tasmota_event(self, event_type: str, data: dict, **kwargs):
        """Handle Tasmota button press events."""
        event = data.get("event")

        # Only react to physical button presses
        if event not in ("SINGLE", "HOLD"):
            return

        # Only alert if house is unoccupied
        if self.get_state(self.HOUSE_OCCUPIED) == "on":
            return

        mac = data.get("mac", "").upper()
        device_name = self._get_device_name_by_mac(mac)

        time_str = self.datetime().strftime("%-I:%M %p")
        self.send_notification(
            targets=["both"],
            message=f"{device_name} was pressed at {time_str} while house is unoccupied!",
            title="Security Alert",
            data={"priority": "high"},
        )
        self.info(f"Alert: {device_name} button pressed while house unoccupied")
