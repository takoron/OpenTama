"""Tests for the pixel-art sprite system."""

import pytest

from opentama import sprites


# --- coverage ---------------------------------------------------------------


@pytest.mark.parametrize(
    "stage", ["egg", "baby", "child", "teen", "adult", "elder"]
)
def test_every_stage_has_a_sprite(stage: str):
    assert stage in sprites.SPRITES
    lines = sprites.render(stage)
    assert lines, f"{stage} rendered empty"


# --- dimensions -------------------------------------------------------------


def test_render_compresses_two_pixels_to_one_line():
    bitmap = sprites.SPRITES["egg"]
    rendered = sprites.render("egg")
    # Source is 12 rows -> 6 lines.
    assert len(rendered) == (len(bitmap) + 1) // 2


def test_every_rendered_line_is_the_sprite_width():
    width = sprites.sprite_width("egg")
    for line in sprites.render("egg"):
        assert len(line) == width


def test_sprite_width_helper_matches_source():
    assert sprites.sprite_width("baby") == len(sprites.SPRITES["baby"][0])


# --- block character choice -------------------------------------------------


def test_only_uses_half_block_characters_and_space():
    allowed = {"█", "▀", "▄", " "}
    for stage in sprites.SPRITES:
        for line in sprites.render(stage):
            extra = set(line) - allowed
            assert not extra, f"unexpected chars in {stage}: {extra!r}"


# --- sick overlay ----------------------------------------------------------


def test_sick_overlay_changes_output():
    healthy = sprites.render("adult")
    sick = sprites.render("adult", sick=True)
    assert healthy != sick


def test_sick_overlay_preserves_dimensions():
    healthy = sprites.render("adult")
    sick = sprites.render("adult", sick=True)
    assert len(healthy) == len(sick)
    for h, s in zip(healthy, sick):
        assert len(h) == len(s)


# --- defensive defaults ----------------------------------------------------


def test_unknown_stage_falls_back_to_egg():
    """Don't blow up on a future stage name we don't have art for."""
    assert sprites.render("supertama") == sprites.render("egg")


# --- distinctness ----------------------------------------------------------


def test_each_stage_has_a_unique_sprite():
    seen: set[tuple[str, ...]] = set()
    for stage in ("egg", "baby", "child", "teen", "adult", "elder"):
        key = tuple(sprites.render(stage))
        assert key not in seen, f"{stage} sprite duplicates an earlier one"
        seen.add(key)
