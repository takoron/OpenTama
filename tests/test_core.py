"""Tests for the Tamagotchi growth/decay/care logic."""

from __future__ import annotations

from typing import Optional

import pytest

from opentama.core import (
    GROWTH_PER_HOUR_AT_OFFICE,
    HAPPINESS_DECAY_AT_OFFICE_PER_HOUR,
    HAPPINESS_DECAY_AWAY_PER_HOUR,
    HUNGER_DECAY_PER_HOUR,
    SICK_THRESHOLD,
    Tamagotchi,
)
from opentama.state import TamaState


class FakeClock:
    """Manual clock for deterministic tick tests."""

    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance_hours(self, h: float) -> None:
        self.t += h * 3600.0

    def advance_seconds(self, s: float) -> None:
        self.t += s


def _make(
    *,
    ssid: Optional[str] = None,
    company_ssid: str = "OfficeWiFi",
    clock_start: float = 1_000_000.0,
    **state_kwargs,
) -> tuple[Tamagotchi, FakeClock]:
    state = TamaState(
        company_ssid=company_ssid,
        last_tick_at=clock_start,  # already anchored
        **state_kwargs,
    )
    clock = FakeClock(clock_start)
    tama = Tamagotchi(state, ssid_provider=lambda: ssid, clock=clock)
    return tama, clock


# --- first tick / hatch -----------------------------------------------------


def test_first_tick_anchors_clock_and_records_hatch():
    state = TamaState(company_ssid="X", last_tick_at=0.0)
    clock = FakeClock(500.0)
    tama = Tamagotchi(state, ssid_provider=lambda: None, clock=clock)

    result = tama.tick()

    assert result.elapsed_hours == 0.0
    assert "hatched" in result.events
    assert state.last_tick_at == 500.0
    assert state.growth_points == 0.0


def test_first_tick_only_hatches_once():
    state = TamaState(company_ssid="X", last_tick_at=0.0)
    clock = FakeClock(500.0)
    tama = Tamagotchi(state, ssid_provider=lambda: None, clock=clock)
    tama.tick()
    state.last_tick_at = 0.0  # simulate a corrupted state
    result = tama.tick()
    assert "hatched" not in result.events


# --- growth at office -------------------------------------------------------


def test_growth_accumulates_when_at_office():
    tama, clock = _make(ssid="OfficeWiFi", growth_points=0.0)
    clock.advance_hours(2.0)
    result = tama.tick()
    assert result.at_office is True
    assert tama.state.growth_points == pytest.approx(GROWTH_PER_HOUR_AT_OFFICE * 2.0)


def test_no_growth_when_off_office():
    tama, clock = _make(ssid="HomeWiFi", growth_points=12.5)
    clock.advance_hours(5.0)
    tama.tick()
    assert tama.state.growth_points == 12.5  # unchanged


def test_growth_when_ssid_none():
    """No WiFi at all is not the office."""
    tama, clock = _make(ssid=None, growth_points=0.0)
    clock.advance_hours(3.0)
    result = tama.tick()
    assert result.at_office is False
    assert tama.state.growth_points == 0.0


def test_no_growth_when_company_ssid_unset():
    tama, clock = _make(
        ssid="OfficeWiFi", company_ssid="", growth_points=0.0
    )
    clock.advance_hours(2.0)
    result = tama.tick()
    assert result.at_office is False
    assert tama.state.growth_points == 0.0


# --- happiness decay --------------------------------------------------------


def test_happiness_decays_faster_when_away():
    tama_a, ca = _make(ssid="OfficeWiFi", happiness=90.0)
    tama_b, cb = _make(ssid="HomeWiFi", happiness=90.0)
    ca.advance_hours(5.0)
    cb.advance_hours(5.0)
    tama_a.tick()
    tama_b.tick()
    assert tama_a.state.happiness > tama_b.state.happiness
    assert tama_a.state.happiness == pytest.approx(
        90.0 - 5.0 * HAPPINESS_DECAY_AT_OFFICE_PER_HOUR
    )
    assert tama_b.state.happiness == pytest.approx(
        90.0 - 5.0 * HAPPINESS_DECAY_AWAY_PER_HOUR
    )


def test_stats_are_clamped_to_zero():
    tama, clock = _make(ssid=None, happiness=1.0, hunger=2.0, energy=3.0)
    clock.advance_hours(1000.0)
    tama.tick()
    assert tama.state.happiness == 0.0
    assert tama.state.hunger == 0.0
    assert tama.state.energy == 0.0


def test_hunger_decays_regardless_of_location():
    tama, clock = _make(ssid="OfficeWiFi", hunger=50.0)
    clock.advance_hours(2.0)
    tama.tick()
    assert tama.state.hunger == pytest.approx(50.0 - HUNGER_DECAY_PER_HOUR * 2.0)


# --- evolution events -------------------------------------------------------


def test_evolution_emits_event_when_crossing_threshold():
    """Crossing from egg (0..10) to baby (>=10) emits evolved_to_baby."""
    tama, clock = _make(ssid="OfficeWiFi", growth_points=8.0)
    # Need 2 more growth points; at 5 gp/h that's 24 minutes.
    clock.advance_hours(0.5)  # +2.5 gp, lands at 10.5
    result = tama.tick()
    assert "evolved_to_baby" in result.events


def test_no_evolution_event_when_stage_unchanged():
    tama, clock = _make(ssid="OfficeWiFi", growth_points=20.0)
    clock.advance_hours(0.5)
    result = tama.tick()
    assert all(not e.startswith("evolved_to_") for e in result.events)


# --- office aggregates ------------------------------------------------------


def test_total_office_seconds_increments():
    tama, clock = _make(ssid="OfficeWiFi", total_office_seconds=0.0)
    clock.advance_hours(1.5)
    tama.tick()
    assert tama.state.total_office_seconds == pytest.approx(1.5 * 3600)


def test_first_hour_milestone_is_recorded_once():
    tama, clock = _make(ssid="OfficeWiFi", total_office_seconds=0.0)
    clock.advance_hours(1.5)
    r1 = tama.tick()
    assert "first_hour" in r1.events
    assert "first_hour" in tama.state.achievements

    clock.advance_hours(1.0)
    r2 = tama.tick()
    assert "first_hour" not in r2.events  # not re-emitted


def test_day_at_office_counter_increments_at_eight_hours():
    tama, clock = _make(ssid="OfficeWiFi", total_office_seconds=0.0)
    clock.advance_hours(8.0)
    result = tama.tick()
    assert tama.state.days_at_office == 1
    assert "day_at_office_1" in result.events


def test_total_office_seconds_does_not_increment_when_away():
    tama, clock = _make(ssid="HomeWiFi", total_office_seconds=1000.0)
    clock.advance_hours(3.0)
    tama.tick()
    assert tama.state.total_office_seconds == 1000.0


# --- care actions -----------------------------------------------------------


def test_feed_increases_hunger_and_clamps():
    tama, _ = _make(hunger=85.0)
    tama.feed()
    assert tama.state.hunger == 100.0  # clamped at 100


def test_play_increases_happiness_and_costs_energy():
    tama, _ = _make(happiness=50.0, energy=50.0)
    tama.play()
    assert tama.state.happiness == 70.0
    assert tama.state.energy == 40.0


def test_play_clamps_energy_at_zero():
    tama, _ = _make(happiness=10.0, energy=5.0)
    tama.play()
    assert tama.state.energy == 0.0


def test_sleep_restores_energy():
    tama, _ = _make(energy=20.0)
    tama.sleep()
    assert tama.state.energy == 60.0


# --- sickness ---------------------------------------------------------------


def test_is_sick_when_any_stat_below_threshold():
    tama, _ = _make(happiness=10.0, hunger=80.0, energy=80.0)
    assert tama.is_sick() is True


def test_is_not_sick_when_all_stats_above_threshold():
    tama, _ = _make(happiness=80.0, hunger=80.0, energy=80.0)
    assert tama.is_sick() is False


def test_sick_event_is_emitted():
    tama, clock = _make(ssid=None, happiness=20.0)
    clock.advance_hours(5.0)
    result = tama.tick()
    assert tama.state.happiness < SICK_THRESHOLD
    assert "sick" in result.events


# --- stage property ---------------------------------------------------------


def test_stage_property_reflects_growth_points():
    tama, _ = _make(growth_points=0.0)
    assert tama.stage.name == "egg"
    tama.state.growth_points = 200.0
    assert tama.stage.name == "teen"


# --- monotonicity / no time travel ------------------------------------------


def test_negative_elapsed_is_treated_as_zero():
    """If the clock somehow moves backwards, nothing should change."""
    state = TamaState(
        company_ssid="OfficeWiFi",
        last_tick_at=1_000_000.0,
        growth_points=10.0,
        happiness=80.0,
    )
    clock = FakeClock(999_900.0)  # earlier than last_tick_at
    tama = Tamagotchi(state, ssid_provider=lambda: "OfficeWiFi", clock=clock)
    tama.tick()
    assert state.growth_points == 10.0
    assert state.happiness == 80.0
    # last_tick_at advances to the new (earlier) time so the system catches up.
    assert state.last_tick_at == 999_900.0
