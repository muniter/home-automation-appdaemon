"""Common base class and utilities for AppDaemon apps."""

import appdaemon.plugins.hass.hassapi as hass

from notify import NotificationRouter, NotifyTarget


class BaseApp(hass.Hass):
    """Base class for all apps with common utilities."""

    def initialize(self):
        """Override in subclass."""
        pass

    def send_notification(
        self,
        targets: list[NotifyTarget],
        message: str,
        title: str = "Home Assistant",
        data: dict | None = None,
    ):
        """Send notification to specified targets.

        Args:
            targets: List of targets ["javier", "andy", "both", "home"]
                - "javier": Javier's devices (phone, tablet if unlocked, laptop if active)
                - "andy": Andy's devices (phone, tablet if interactive)
                - "both": Both people's devices
                - "home": All devices for people home + active home devices (TV, etc.)
            message: Notification message
            title: Notification title
            data: Optional data dict (for actions, priority, etc.)
        """
        router = NotificationRouter(self.get_state)
        services = router.resolve_targets(targets)

        if not services:
            return

        # Build service data
        service_data: dict = {
            "message": message,
            "title": title,
        }
        if data:
            service_data["data"] = data

        # Call each notify service directly
        for service in services:
            self.call_service(f"notify/{service}", **service_data)

    def notify_phone(self, message: str, title: str = "Home Assistant"):
        """Send notification to Javier's phone (legacy helper)."""
        self.send_notification(["javier"], message, title)

    # TTS Entities
    TTS_FIRST_FLOOR = "media_player.first_floor_xiaomi_gateway"
    TTS_SECOND_FLOOR = "media_player.second_floor_xiaomi_gateway"

    def tts_first_floor(self, message: str, language: str = "es-ES"):
        """Play TTS message on first floor Xiaomi gateway."""
        self._tts_speak(self.TTS_FIRST_FLOOR, message, language)

    def tts_second_floor(self, message: str, language: str = "es-ES"):
        """Play TTS message on second floor Xiaomi gateway."""
        self._tts_speak(self.TTS_SECOND_FLOOR, message, language)

    def tts_all(self, message: str, language: str = "es-ES"):
        """Play TTS message on all floors."""
        self._tts_speak(self.TTS_FIRST_FLOOR, message, language)
        self._tts_speak(self.TTS_SECOND_FLOOR, message, language)

    def _tts_speak(self, entity_id: str, message: str, language: str):
        """Internal helper to call TTS service."""
        self.call_service(
            "tts/cloud_say",
            entity_id=entity_id,
            message=message,
            language=language,
        )

    def debug(self, message: str):
        """Log debug message with app name prefix."""
        self.log(f"[{self.__class__.__name__}] {message}", level="DEBUG")

    def info(self, message: str):
        """Log info message with app name prefix."""
        self.log(f"[{self.__class__.__name__}] {message}", level="INFO")
