"""Tests for the display backends (monokuro / iro / wide)."""

import pytest

from opentama import displays
from opentama.core import Tamagotchi
from opentama.plugins.api import StateView
from opentama.state import TamaState


def _view(stage: str = "baby", **overrides) -> StateView:
    base = dict(
        name="たまお",
        stage=stage,
        growth_points=42,
        happiness=72,
        hunger=55,
        energy=63,
    )
    base.update(overrides)
    return StateView(**base)


def test_registry_lists_three_displays():
    assert set(displays.DISPLAYS.keys()) == {"monokuro", "iro", "wide"}


@pytest.mark.parametrize("name", ["monokuro", "iro", "wide"])
def test_render_returns_non_empty_multiline(name: str):
    out = displays.get(name).render(_view())
    assert isinstance(out, str)
    assert "\n" in out
    # The pet's name should appear in every display.
    assert "たまお" in out


@pytest.mark.parametrize("name", ["monokuro", "iro", "wide"])
def test_render_for_every_stage(name: str):
    for stage in ("egg", "baby", "child", "teen", "adult", "elder"):
        out = displays.get(name).render(_view(stage=stage))
        assert out.strip(), f"{name} produced empty output for stage {stage}"


def test_each_display_is_visually_distinct():
    """Sanity check: the three displays produce different output."""
    v = _view()
    a = displays.get("monokuro").render(v)
    b = displays.get("iro").render(v)
    c = displays.get("wide").render(v)
    assert a != b != c != a


def test_unknown_display_name_raises():
    with pytest.raises(KeyError):
        displays.get("nonexistent")


def test_render_with_tama_helper():
    state = TamaState(
        name="Bert",
        company_ssid="",
        last_tick_at=1.0,
        happiness=90.0,
        hunger=80.0,
        energy=70.0,
        growth_points=210.0,
    )
    tama = Tamagotchi(state, ssid_provider=lambda: None, clock=lambda: 1.0)
    out = displays.render_with_tama("iro", tama)
    assert "Bert" in out
    assert "teen" in out  # growth_points=210 → teen


def test_low_stats_show_sick_mood_in_wide():
    """The wide display should change icons when the pet is sick."""
    healthy = displays.get("wide").render(_view(happiness=90, hunger=80, energy=70))
    sick = displays.get("wide").render(_view(happiness=10, hunger=80, energy=70))
    assert healthy != sick
