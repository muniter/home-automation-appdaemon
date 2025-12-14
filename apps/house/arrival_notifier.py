"""Arrival notification automation.

Notifies Javier when Andy arrives home, but skips notification if they
arrived together (within 5 minute window).

When Andy arrives:
- If Javier was already home (5+ min) → notify Javier immediately
- If Javier just arrived too → skip (arrived together)
- If Javier not home → wait 5 min, notify Javier if he doesn't arrive
"""

from common import BaseApp

# Time window to consider "arrived together"
ARRIVAL_TOGETHER_WINDOW_MINUTES = 5


class ArrivalNotifier(BaseApp):

    JAVIER = "person.javier"
    ANDY = "person.andy"

    def initialize(self):
        self.andy_arrival_timer = None

        self.listen_state(self.on_javier_arrived, self.JAVIER, new="home")
        self.listen_state(self.on_andy_arrived, self.ANDY, new="home")

        self.info("Arrival notifier initialized")

    def on_javier_arrived(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Javier arrived - cancel Andy's pending notification if any."""
        if old == new:
            return
        self._cancel_andy_arrival_timer()

    def on_andy_arrived(self, entity: str, attribute: str, old: str, new: str, **kwargs):
        """Andy arrived - check if we should notify."""
        if old == new:
            return
        self._check_andy_arrival_notification()

    def _check_andy_arrival_notification(self):
        """Check if we should notify about Andy's arrival."""
        # If Javier is home, check how long he's been home
        if self.get_state(self.JAVIER) == "home":
            last_changed = self.get_state(self.JAVIER, attribute="last_changed")
            if last_changed and isinstance(last_changed, str):
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                changed = self.convert_utc(last_changed)
                minutes_home = (now - changed).total_seconds() / 60

                if minutes_home > ARRIVAL_TOGETHER_WINDOW_MINUTES:
                    # Javier was already home - notify immediately
                    self._send_andy_arrival_notification()
                else:
                    # Javier just arrived too - they arrived together, skip
                    self.info("Andy and Javier arrived together, skipping notification")
                return

        # Javier not home - wait to see if he arrives
        self._cancel_andy_arrival_timer()
        self.andy_arrival_timer = self.run_in(
            self._on_andy_arrival_timer,
            ARRIVAL_TOGETHER_WINDOW_MINUTES * 60,
        )
        self.info(f"Andy arrived, waiting {ARRIVAL_TOGETHER_WINDOW_MINUTES}min for Javier")

    def _on_andy_arrival_timer(self, kwargs):
        """Timer expired - Javier didn't arrive, send notification."""
        self.andy_arrival_timer = None
        self._send_andy_arrival_notification()

    def _send_andy_arrival_notification(self):
        """Send notification to Javier that Andy arrived."""
        time_str = self.datetime().strftime("%-I:%M %p")
        self.send_notification(
            targets=["javier"],
            message=f"{time_str} Andy is now at home",
            title="Arrival / Departure",
            data={"tag": "house_arrived_home"},
        )
        self.info("Sent Andy arrival notification to Javier")

    def _cancel_andy_arrival_timer(self):
        """Cancel pending Andy arrival notification timer."""
        if self.andy_arrival_timer:
            self.cancel_timer(self.andy_arrival_timer)
            self.andy_arrival_timer = None
            self.info("Cancelled Andy arrival timer - Javier arrived")
