"""Tests for the colour Takoron portrait (opentama.art)."""

import re

import pytest

from opentama import art


STAGES = ["egg", "baby", "child", "teen", "adult", "elder"]


# --- grids ------------------------------------------------------------------


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_has_a_grid(stage):
    assert stage in art.GRIDS
    assert art.GRIDS[stage], f"{stage} grid empty"


@pytest.mark.parametrize("stage", STAGES)
def test_grid_rows_are_uniform_width(stage):
    rows = art.GRIDS[stage]
    widths = {len(r) for r in rows}
    assert len(widths) == 1, f"{stage} has ragged rows: {widths}"


def test_all_grid_keys_are_in_palette_or_transparent():
    allowed = set(art.PALETTE) | {"."}
    for stage, rows in art.GRIDS.items():
        for row in rows:
            extra = set(row) - allowed
            assert not extra, f"{stage} uses unknown keys: {extra}"


# --- stage composition ------------------------------------------------------


def test_egg_is_plain_dough():
    """Egg has no face, toppings, or flake — only dough + outline."""
    flat = "".join(art.GRIDS["egg"])
    for feature in ("F", "e", "c", "m", "t", "g", "r", "k", "K", "j"):
        assert feature not in flat, f"egg unexpectedly contains {feature!r}"


def test_baby_has_face_but_no_toppings_or_flake():
    flat = "".join(art.GRIDS["baby"])
    assert "e" in flat  # eyes
    assert "c" in flat  # cheeks
    assert "g" not in flat and "r" not in flat  # no toppings
    assert "k" not in flat  # no flake


def test_child_has_toppings_but_no_flake():
    flat = "".join(art.GRIDS["child"])
    assert "g" in flat or "r" in flat
    assert "k" not in flat


def test_adult_has_everything():
    flat = "".join(art.GRIDS["adult"])
    for feature in ("F", "e", "c", "m", "g", "r", "k"):
        assert feature in flat, f"adult missing {feature!r}"


def test_eyes_have_a_white_catchlight():
    # Big round open eyes carry a white highlight.
    assert "w" in "".join(art.GRIDS["adult"])
    assert "w" in "".join(art.GRIDS["baby"])


def test_elder_has_steam():
    assert "s" in "".join(art.GRIDS["elder"])


def test_baby_has_omega_mouth_others_open():
    # Baby keeps the ω (おちょぼ口): mouth colour but no open interior.
    baby = "".join(art.GRIDS["baby"])
    assert "m" in baby and "t" not in baby
    # child / teen / adult / elder have an open mouth (tongue/interior).
    for stage in ("child", "teen", "adult", "elder"):
        flat = "".join(art.GRIDS[stage])
        assert "m" in flat and "t" in flat, f"{stage} should have an open mouth"
    # The faceless egg has neither.
    egg = "".join(art.GRIDS["egg"])
    assert "m" not in egg and "t" not in egg


# --- rendering --------------------------------------------------------------


@pytest.mark.parametrize("stage", STAGES)
def test_render_color_emits_ansi(stage):
    out = "\n".join(art.render_color(stage))
    assert "\x1b[38;2;" in out  # at least one truecolor fg escape
    assert "\x1b[0m" in out      # and a reset


@pytest.mark.parametrize("stage", STAGES)
def test_render_mono_has_no_ansi(stage):
    out = "\n".join(art.render_mono(stage))
    assert "\x1b" not in out


def test_color_render_height_is_half_grid():
    grid = art.GRIDS["adult"]
    rendered = art.render_color("adult")
    assert len(rendered) == (len(grid) + 1) // 2


def test_adult_color_contains_expected_palette_colors():
    out = "\n".join(art.render_color("adult"))
    for key in ("m", "t", "c", "g", "r", "e", "w"):
        r, g, b = art.PALETTE[key]
        assert f"{r};{g};{b}" in out, f"missing colour for {key}"


def test_unknown_stage_falls_back_to_egg():
    assert art.render_color("nope") == art.render_color("egg")


# --- supports_color ---------------------------------------------------------


def test_supports_color_respects_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert art.supports_color() is False


def test_supports_color_respects_force_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert art.supports_color() is True
