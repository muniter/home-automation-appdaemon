"""Vacation lights - fake presence while away.

When vacation mode is ON, simulate someone being home by turning lights on/off
in a natural-looking pattern.

Pattern:
    - ~30 minutes after sunset (±15 min random): turn on living room lights
    - Every ~45 minutes: turn off briefly (1-2 min), then back on
      This resets the left_on_notifier timer and looks more natural
    - After ~2 hours total: turn off for the night

The brief off/on cycles ensure we never trigger the 2-hour vacation alert
in left_on_notifier, while making the house look lived-in.
"""

import random

from common import BaseApp

# How long after sunset to turn on lights (base minutes, randomized ±15)
SUNSET_DELAY_BASE_MINUTES = 30
SUNSET_DELAY_VARIANCE_MINUTES = 15

# How often to cycle lights off/on (base minutes)
CYCLE_INTERVAL_BASE_MINUTES = 45
CYCLE_INTERVAL_VARIANCE_MINUTES = 10

# How long to keep lights off during cycle (seconds)
CYCLE_OFF_SECONDS = 90

# Total duration to keep lights on before turning off for the night (minutes)
TOTAL_ON_DURATION_MINUTES = 120


class VacationLights(BaseApp):

    VACATION_MODE = "input_boolean.vacation_mode"
    LIVING_ROOM_LIGHTS = "group.living_room_lights_and_switches"

    def initialize(self):
        self.sunset_timer = None
        self.cycle_timer = None
        self.turn_on_timer = None
        self.end_timer = None
        self.session_start = None

        # React to vacation mode changes
        self.listen_state(self._on_vacation_mode_change, self.VACATION_MODE)

        # React to sunset when in vacation mode
        self.run_at_sunset(self._on_sunset)

        # If vacation mode is already on, check if we should be running
        if self.get_state(self.VACATION_MODE) == "on":
            self._check_current_state()

        self.info("Vacation lights initialized")

    def _on_vacation_mode_change(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Vacation mode changed."""
        if old == new:
            return

        if new == "on":
            self.info("Vacation mode ON - will start lights at sunset")
            self._check_current_state()
        else:
            self.info("Vacation mode OFF - stopping vacation lights")
            self._cancel_all_timers()
            # Turn off lights if we had them on
            self.call_service("homeassistant/turn_off", entity_id=self.LIVING_ROOM_LIGHTS)

    def _check_current_state(self):
        """Check if we should start lights now (e.g., vacation mode enabled after sunset, or restart)."""
        if self.get_state(self.VACATION_MODE) != "on":
            return

        # If lights are already on, we probably restarted mid-session
        # Resume the cycling pattern
        if self.get_state(self.LIVING_ROOM_LIGHTS) == "on" and self.sun_down():
            self.info("Lights already on after restart, resuming cycle pattern")
            self._schedule_next_cycle()
            # Schedule end of session (assume we're partway through, give 1 hour)
            self.end_timer = self.run_in(self._end_session, 60 * 60)
            return

        if self.sun_down():
            # Already past sunset, start lights with short delay
            delay = random.randint(1, 5) * 60  # 1-5 minutes
            self.sunset_timer = self.run_in(self._start_lights, delay)
            self.info(f"Past sunset, starting lights in {delay // 60} minutes")

    def _on_sunset(self, kwargs):
        """Sunset occurred - start lights if in vacation mode."""
        if self.get_state(self.VACATION_MODE) != "on":
            return

        # Random delay after sunset
        delay_minutes = SUNSET_DELAY_BASE_MINUTES + random.randint(
            -SUNSET_DELAY_VARIANCE_MINUTES, SUNSET_DELAY_VARIANCE_MINUTES
        )
        delay_seconds = delay_minutes * 60

        self._cancel_all_timers()
        self.sunset_timer = self.run_in(self._start_lights, delay_seconds)
        self.info(f"Sunset detected, will turn on lights in {delay_minutes} minutes")

    def _start_lights(self, kwargs):
        """Turn on lights and start cycling pattern."""
        if self.get_state(self.VACATION_MODE) != "on":
            return

        self.session_start = self.datetime()
        self.call_service("homeassistant/turn_on", entity_id=self.LIVING_ROOM_LIGHTS)
        self.info("Vacation lights ON")

        # Schedule first cycle
        self._schedule_next_cycle()

        # Schedule end of session
        self.end_timer = self.run_in(self._end_session, TOTAL_ON_DURATION_MINUTES * 60)

    def _schedule_next_cycle(self):
        """Schedule the next off/on cycle."""
        # Random interval for next cycle
        interval_minutes = CYCLE_INTERVAL_BASE_MINUTES + random.randint(
            -CYCLE_INTERVAL_VARIANCE_MINUTES, CYCLE_INTERVAL_VARIANCE_MINUTES
        )
        self.cycle_timer = self.run_in(self._cycle_off, interval_minutes * 60)
        self.debug(f"Next cycle in {interval_minutes} minutes")

    def _cycle_off(self, kwargs):
        """Turn off lights briefly."""
        if self.get_state(self.VACATION_MODE) != "on":
            return

        self.call_service("homeassistant/turn_off", entity_id=self.LIVING_ROOM_LIGHTS)
        self.debug("Cycle: lights OFF")

        # Schedule turn back on
        self.turn_on_timer = self.run_in(self._cycle_on, CYCLE_OFF_SECONDS)

    def _cycle_on(self, kwargs):
        """Turn lights back on after brief off period."""
        if self.get_state(self.VACATION_MODE) != "on":
            return

        self.call_service("homeassistant/turn_on", entity_id=self.LIVING_ROOM_LIGHTS)
        self.debug("Cycle: lights ON")

        # Schedule next cycle
        self._schedule_next_cycle()

    def _end_session(self, kwargs):
        """End the vacation lights session for the night."""
        self._cancel_all_timers()
        self.call_service("homeassistant/turn_off", entity_id=self.LIVING_ROOM_LIGHTS)
        self.info("Vacation lights session ended for tonight")

    def _cancel_all_timers(self):
        """Cancel all pending timers."""
        for timer_name in ["sunset_timer", "cycle_timer", "turn_on_timer", "end_timer"]:
            timer = getattr(self, timer_name, None)
            if timer:
                self.cancel_timer(timer)
                setattr(self, timer_name, None)
