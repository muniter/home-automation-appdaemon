"""Notification routing logic.

Determines where to send notifications based on targets and device states.

Each target has a `conditions` dict mapping tags to lambda functions.
When a notification is sent to a target (e.g., ["javier"]), the router:
1. Finds all devices with matching tags
2. For each device, evaluates the condition lambda for that tag
3. If any matching tag's condition passes, the device receives the notification

This allows different conditions per tag. For example, a work laptop might:
- Receive "javier" notifications when active (regardless of location)
- Receive "home" notifications only when active AND user is home
"""

from typing import Literal, Callable, Any

NotifyTarget = Literal["javier", "andy", "both", "home"]

# Type for AppDaemon's get_state function
GetStateFunc = Callable[..., Any]

# Type for condition lambda
ConditionFunc = Callable[[GetStateFunc], bool]


class NotificationRouter:
    """Routes notifications to the right services based on conditions."""

    TARGETS: list[dict[str, Any]] = [
        # Javier's phone - if home
        {
            "service": "mobile_app_javier_phone",
            "conditions": {
                "javier": lambda get_state: get_state("person.javier") == "home",
                "both": lambda get_state: get_state("person.javier") == "home",
                "home": lambda get_state: get_state("person.javier") == "home",
            },
            "tags": ["javier", "both", "home"],
        },
        # Andy's phone - if home
        {
            "service": "mobile_app_andy_phone",
            "conditions": {
                "andy": lambda get_state: get_state("person.andy") == "home",
                "both": lambda get_state: get_state("person.andy") == "home",
                "home": lambda get_state: get_state("person.andy") == "home",
            },
            "tags": ["andy", "both", "home"],
        },
        # Javier's tablet - if unlocked
        {
            "service": "mobile_app_javier_tablet",
            "conditions": {
                "javier": lambda get_state: get_state("binary_sensor.javier_tablet_device_locked") == "off",
                "home": lambda get_state: get_state("binary_sensor.javier_tablet_device_locked") == "off",
            },
            "tags": ["javier", "home"],
        },
        # Andy's tablet - if interactive (screen on)
        {
            "service": "mobile_app_andy_tablet",
            "conditions": {
                "andy": lambda get_state: get_state("binary_sensor.andy_tablet_interactive") == "on",
                "home": lambda get_state: get_state("binary_sensor.andy_tablet_interactive") == "on",
            },
            "tags": ["andy", "home"],
        },
        # Living room TV - if on
        {
            "service": "living_room_tv",
            "conditions": {
                "home": lambda get_state: get_state("media_player.living_room_tv") == "on",
            },
            "tags": ["home"],
        },
        # Javier's work laptop - active for javier, active+home for home
        {
            "service": "mobile_app_javier_work_laptop",
            "conditions": {
                "javier": lambda get_state: get_state("binary_sensor.javier_work_laptop_active") == "on",
                "home": lambda get_state: (
                    get_state("binary_sensor.javier_work_laptop_active") == "on"
                    and get_state("person.javier") == "home"
                ),
            },
            "tags": ["javier", "home"],
        },
    ]

    def __init__(self, get_state: GetStateFunc):
        """Initialize with a state getter function.

        Args:
            get_state: Function that takes entity_id and returns its state
        """
        self.get_state = get_state

    def resolve_targets(self, targets: list[NotifyTarget]) -> set[str]:
        """Resolve target names to actual notify services based on conditions.

        Args:
            targets: List of targets like ["javier", "home", "both"]

        Returns:
            Set of notify service names to call
        """
        services: set[str] = set()

        for target_def in self.TARGETS:
            # Find matching tags
            matching_tags = [tag for tag in target_def["tags"] if tag in targets]
            if not matching_tags:
                continue

            # Check if any matching tag's condition passes (OR logic)
            conditions = target_def.get("conditions", {})
            should_notify = False

            for tag in matching_tags:
                condition = conditions.get(tag)
                # If no condition for this tag, or condition passes -> notify
                if condition is None or condition(self.get_state):
                    should_notify = True
                    break

            if should_notify:
                services.add(target_def["service"])

        return services
