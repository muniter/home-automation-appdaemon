"""Vacation mode automation.

Detects when someone is far from home and offers to enable vacation mode.

Detection Logic:
    Listens to geocoded_location sensor changes (reacts instantly when country
    changes, e.g., landing in another country). We check if BOTH people are far
    from home using two methods:
    
    1. Country check (preferred): If the geocoded_location sensor has a Country
       attribute and it's not Panama (home country), they're abroad.
    
    2. Distance fallback: If country data unavailable, calculate GPS distance.
       If > 100km from home, consider them far away.
    
    We use these instead of "not_home" state because "not_home" just means
    outside the home zone radius - could be at the grocery store.

Auto-disable:
    When house becomes occupied again (someone returns), automatically disable
    vacation mode - they're clearly back from vacation.

Notification Actions:
    - "Enable" → turns on vacation_mode
    - Dismiss/ignore → nothing happens (can ask again next time)
"""

from math import asin, cos, radians, sin, sqrt

from common import BaseApp

# Home country ISO code
HOME_COUNTRY = "PA"  # Panama

# Distance threshold to consider "far from home" (in kilometers)
# Used as fallback when country data unavailable
FAR_FROM_HOME_KM = 100

# Action identifier for the notification
ACTION_ENABLE_VACATION = "ENABLE_VACATION_MODE"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers.

    Uses the Haversine formula for great-circle distance.
    """
    # Earth's radius in kilometers
    R = 6371

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return R * c


class VacationMode(BaseApp):

    VACATION_MODE = "input_boolean.vacation_mode"
    HOUSE_OCCUPIED = "input_boolean.house_occupied"

    JAVIER_PHONE = "device_tracker.javier_phone"
    ANDY_PHONE = "device_tracker.andy_phone"
    JAVIER_GEOCODED = "sensor.javier_phone_geocoded_location"
    ANDY_GEOCODED = "sensor.andy_phone_geocoded_location"
    HOME_ZONE = "zone.home"

    def initialize(self):
        # Track if we've already sent a notification this "trip"
        # Reset when someone comes home
        self.notification_sent = False

        # React instantly to geocoded location changes (country attribute)
        # Android uses lowercase, iOS uses title case
        self.listen_state(
            self._on_location_change,
            self.JAVIER_GEOCODED,
            attribute="iso_country_code",  # Android
        )
        self.listen_state(
            self._on_location_change,
            self.ANDY_GEOCODED,
            attribute="ISO Country Code",  # iOS
        )

        # Also check on startup
        self.run_in(self._check_vacation, 5)

        # Auto-disable vacation mode when house becomes occupied
        self.listen_state(
            self._on_house_occupied,
            self.HOUSE_OCCUPIED,
            new="on",
        )

        # Listen for notification action response
        self.listen_event(self._on_notification_action, event="mobile_app_notification_action")

        self.info("Vacation mode initialized")

    def _get_home_coords(self) -> tuple[float, float] | None:
        """Get home zone coordinates."""
        state = self.get_state(self.HOME_ZONE, attribute="all")
        if not state:
            return None
        attrs = state.get("attributes", {})
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        if lat is None or lon is None:
            return None
        return (lat, lon)

    def _get_phone_coords(self, entity_id: str) -> tuple[float, float] | None:
        """Get phone GPS coordinates."""
        state = self.get_state(entity_id, attribute="all")
        if not state:
            return None
        attrs = state.get("attributes", {})
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        if lat is None or lon is None:
            return None
        return (lat, lon)

    def _is_person_far(self, geocoded_entity: str, tracker_entity: str, name: str) -> bool:
        """Check if a person is far from home.
        
        First tries country from geocoded location, falls back to GPS distance.
        """
        # Try country check first (more reliable when available)
        geocoded = self.get_state(geocoded_entity, attribute="all")
        if geocoded:
            attrs = geocoded.get("attributes", {})
            # iOS uses "ISO Country Code", Android uses "iso_country_code"
            country_code = attrs.get("ISO Country Code") or attrs.get("iso_country_code")
            if country_code:
                is_abroad = country_code != HOME_COUNTRY
                self.debug(f"{name} country: {country_code}, abroad={is_abroad}")
                return is_abroad

        # Fallback to distance calculation
        home = self._get_home_coords()
        if not home:
            return False

        coords = self._get_phone_coords(tracker_entity)
        if not coords:
            return False

        distance = haversine_distance(home[0], home[1], coords[0], coords[1])
        is_far = distance > FAR_FROM_HOME_KM
        self.debug(f"{name} distance from home: {distance:.1f}km, far={is_far}")
        return is_far

    def _on_location_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Geocoded location country changed - check if we should suggest vacation mode."""
        if old == new:
            return
        self.info(f"Location country changed: {entity} {old} -> {new}")
        self._check_vacation(kwargs)

    def _check_vacation(self, kwargs):
        """Check if both people are far from home."""
        # Skip if vacation mode already on
        if self.get_state(self.VACATION_MODE) == "on":
            return

        # Skip if we already sent notification this trip
        if self.notification_sent:
            return

        javier_far = self._is_person_far(self.JAVIER_GEOCODED, self.JAVIER_PHONE, "Javier")
        andy_far = self._is_person_far(self.ANDY_GEOCODED, self.ANDY_PHONE, "Andy")

        # Only suggest vacation mode if BOTH are far
        if javier_far and andy_far:
            self._send_vacation_notification()

    def _send_vacation_notification(self):
        """Send actionable notification to enable vacation mode."""
        self.notification_sent = True

        self.send_notification(
            targets=["javier"],
            title="Modo Vacaciones",
            message="Detectamos que están lejos de casa. ¿Activar modo vacaciones?",
            data={
                "actions": [
                    {
                        "action": ACTION_ENABLE_VACATION,
                        "title": "Activar",
                    },
                ],
            },
        )
        self.info("Sent vacation mode notification")

    def _on_notification_action(self, event_name: str, data: dict, kwargs):
        """Handle notification action response."""
        action = data.get("action")
        if action == ACTION_ENABLE_VACATION:
            self.call_service("input_boolean/turn_on", entity_id=self.VACATION_MODE)
            self.info("Vacation mode enabled via notification")

            # Confirm to user
            self.send_notification(
                targets=["both"],
                title="Modo Vacaciones",
                message="Modo vacaciones activado",
            )

    def _on_house_occupied(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """House became occupied - disable vacation mode."""
        # Reset notification flag so we can ask again on next trip
        self.notification_sent = False

        if self.get_state(self.VACATION_MODE) == "on":
            self.call_service("input_boolean/turn_off", entity_id=self.VACATION_MODE)
            self.info("Vacation mode auto-disabled (house occupied)")

            self.send_notification(
                targets=["both"],
                title="Modo Vacaciones",
                message="Modo vacaciones desactivado automáticamente - bienvenidos a casa",
            )
