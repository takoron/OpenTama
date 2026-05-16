"""Tests for stage selection."""

from opentama.stages import STAGES, stage_for


def test_stages_are_in_increasing_order():
    thresholds = [s.min_growth for s in STAGES]
    assert thresholds == sorted(thresholds)
    assert thresholds[0] == 0


def test_zero_growth_is_egg():
    assert stage_for(0).name == "egg"


def test_below_first_threshold_returns_first_stage():
    # Even negative growth (shouldn't happen, but be defensive) returns egg.
    assert stage_for(-100).name == "egg"


def test_each_stage_threshold_is_inclusive():
    for stage in STAGES:
        assert stage_for(stage.min_growth).name == stage.name


def test_just_below_threshold_returns_previous_stage():
    # baby starts at 10, so 9 should still be egg.
    assert stage_for(9).name == "egg"
    # child starts at 50, so 49 should still be baby.
    assert stage_for(49).name == "baby"


def test_high_growth_returns_final_stage():
    assert stage_for(10**9).name == STAGES[-1].name


def test_all_stages_have_art():
    for stage in STAGES:
        assert stage.art.strip(), f"{stage.name} has empty art"
