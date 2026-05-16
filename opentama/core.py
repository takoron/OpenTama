"""The core OpenTama lifecycle: growth, decay, and care actions.

The :class:`Tamagotchi` class is intentionally pure with respect to I/O:
the WiFi SSID lookup and the clock are injected so tests can drive them
deterministically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .stages import Stage, stage_for
from .state import TamaState


# --- tunables ---------------------------------------------------------------
# All decay/growth rates are expressed per hour so callers can tick at
# whatever cadence they like (status checks, cron, shell hook, ...).

GROWTH_PER_HOUR_AT_OFFICE = 5.0
HAPPINESS_DECAY_AT_OFFICE_PER_HOUR = 1.0
HAPPINESS_DECAY_AWAY_PER_HOUR = 4.0
HUNGER_DECAY_PER_HOUR = 5.0
ENERGY_DECAY_PER_HOUR = 4.0

FEED_HUNGER_DELTA = 30.0
PLAY_HAPPINESS_DELTA = 20.0
PLAY_ENERGY_COST = 10.0
SLEEP_ENERGY_DELTA = 40.0

# Stats below this threshold mark the pet as "in trouble".
SICK_THRESHOLD = 15.0


@dataclass
class TickResult:
    """Summary of what happened during a tick."""

    elapsed_hours: float
    at_office: bool
    ssid: Optional[str]
    stage: str
    events: list[str] = field(default_factory=list)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class Tamagotchi:
    """A virtual pet whose growth depends on being on the office WiFi."""

    def __init__(
        self,
        state: TamaState,
        ssid_provider: Callable[[], Optional[str]] = lambda: None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.state = state
        self.ssid_provider = ssid_provider
        self.clock = clock

    # --- properties -------------------------------------------------------

    @property
    def stage(self) -> Stage:
        return stage_for(int(self.state.growth_points))

    def current_ssid(self) -> Optional[str]:
        return self.ssid_provider()

    def is_at_office(self) -> bool:
        ssid = self.current_ssid()
        return bool(self.state.company_ssid) and ssid == self.state.company_ssid

    def is_sick(self) -> bool:
        s = self.state
        return min(s.happiness, s.hunger, s.energy) <= SICK_THRESHOLD

    # --- main lifecycle ---------------------------------------------------

    def tick(self) -> TickResult:
        """Advance the simulation to ``now``.

        Idempotent: calling ``tick`` twice in quick succession the second
        call simply records ~0 hours elapsed.
        """
        now = self.clock()
        events: list[str] = []
        prev_stage_name = self.stage.name
        ssid = self.current_ssid()
        at_office = bool(self.state.company_ssid) and ssid == self.state.company_ssid

        # First tick after init: just anchor the clock.
        if self.state.last_tick_at <= 0:
            self.state.last_tick_at = now
            if "hatched" not in self.state.achievements:
                self.state.achievements.append("hatched")
                events.append("hatched")
            return TickResult(0.0, at_office, ssid, self.stage.name, events)

        elapsed_seconds = max(0.0, now - self.state.last_tick_at)
        elapsed_hours = elapsed_seconds / 3600.0

        if at_office:
            self.state.growth_points += GROWTH_PER_HOUR_AT_OFFICE * elapsed_hours
            self.state.happiness = _clamp(
                self.state.happiness - HAPPINESS_DECAY_AT_OFFICE_PER_HOUR * elapsed_hours
            )
            prev_office_seconds = self.state.total_office_seconds
            self.state.total_office_seconds += elapsed_seconds

            # Milestone: first hour at office.
            if (
                prev_office_seconds < 3600.0 <= self.state.total_office_seconds
                and "first_hour" not in self.state.achievements
            ):
                self.state.achievements.append("first_hour")
                events.append("first_hour")

            # Day-counter: rough threshold of 8 office hours = 1 day.
            new_days = int(self.state.total_office_seconds // (8 * 3600))
            if new_days > self.state.days_at_office:
                self.state.days_at_office = new_days
                events.append(f"day_at_office_{new_days}")
        else:
            self.state.happiness = _clamp(
                self.state.happiness - HAPPINESS_DECAY_AWAY_PER_HOUR * elapsed_hours
            )

        # Hunger and energy decay regardless of location.
        self.state.hunger = _clamp(
            self.state.hunger - HUNGER_DECAY_PER_HOUR * elapsed_hours
        )
        self.state.energy = _clamp(
            self.state.energy - ENERGY_DECAY_PER_HOUR * elapsed_hours
        )

        self.state.last_tick_at = now

        new_stage_name = self.stage.name
        if new_stage_name != prev_stage_name:
            events.append(f"evolved_to_{new_stage_name}")

        if self.is_sick():
            events.append("sick")

        return TickResult(elapsed_hours, at_office, ssid, new_stage_name, events)

    # --- care actions -----------------------------------------------------

    def feed(self) -> None:
        self.state.hunger = _clamp(self.state.hunger + FEED_HUNGER_DELTA)

    def play(self) -> None:
        self.state.happiness = _clamp(self.state.happiness + PLAY_HAPPINESS_DELTA)
        self.state.energy = _clamp(self.state.energy - PLAY_ENERGY_COST)

    def sleep(self) -> None:
        self.state.energy = _clamp(self.state.energy + SLEEP_ENERGY_DELTA)
