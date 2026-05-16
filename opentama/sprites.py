"""Tamagotchi-style pixel sprites for the pet.

Each stage is a small monochrome bitmap defined as a list of strings
where ``#`` is an "on" pixel and any other character is "off". The
:func:`render` function compresses two vertical pixels into one
terminal cell using the half-block characters ``▀ ▄ █``, so a 12x12
sprite fits in 6 terminal rows.

This is what makes OpenTama actually feel like a Tamagotchi: the
drawing is small enough that it could plausibly run on the LCD of a
real ガラケー or the original 32x16 Tamagotchi display.
"""

from __future__ import annotations

from typing import Iterable, List


# ---------------------------------------------------------------------------
# Sprite bitmaps — 12 wide × 12 tall = 6 rendered terminal rows.
# Designed so each stage is visually distinct and silhouette-readable.
# ---------------------------------------------------------------------------


SPRITES: dict[str, list[str]] = {
    "egg": [
        "....####....",
        "...######...",
        "..########..",
        ".##########.",
        ".##########.",
        ".####.#####.",
        ".##########.",
        ".##########.",
        ".########.#.",
        "..########..",
        "...######...",
        "....####....",
    ],
    "baby": [
        "............",
        "....####....",
        "...######...",
        "..########..",
        "..##.##.##..",  # two eye dots
        "..########..",
        "..########..",
        "...######...",
        "....####....",
        "....#..#....",
        "....#..#....",
        "............",
    ],
    "child": [
        "....####....",
        "...######...",
        "..########..",
        "..##.##.##..",  # eyes
        "..########..",
        "..##.##.##..",  # mouth row (just a hint)
        "..########..",
        "..########..",
        "...######...",
        "...#....#...",
        "..##....##..",
        "............",
    ],
    "teen": [
        "...#....#...",  # antennae / horns
        "...##..##...",
        "...######...",
        "..########..",
        ".####.######",  # offset eye highlight
        ".##########.",
        ".####.#####.",
        ".##########.",
        "..########..",
        "..##....##..",
        ".####..####.",
        "............",
    ],
    "adult": [
        "..##....##..",  # tall ears
        ".####..####.",
        ".##########.",
        "##.######.##",  # eyes inset
        "############",
        "##........##",  # mouth wide
        "############",
        ".##########.",
        ".####..####.",
        ".####..####.",
        "..##....##..",
        "............",
    ],
    "elder": [
        "..####..####",  # eyebrows
        ".##########.",
        ".##.####.##.",  # eyes
        ".##########.",
        ".###.##.###.",  # mustache start
        "############",
        ".###....###.",  # mustache row
        ".##########.",
        ".####..####.",
        "..##.##.##..",
        "..##....##..",
        "............",
    ],
}


# A "sick" overlay: same silhouette as the current stage but with sweat
# drops added in the corners. Applied by :func:`render` when ``sick=True``.
_SICK_OVERLAY = [
    "#..........#",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _overlay(base: list[str], overlay: list[str]) -> list[str]:
    out = []
    for b, o in zip(base, overlay):
        merged = "".join(
            "#" if (bi == "#" or oi == "#") else "."
            for bi, oi in zip(b, o)
        )
        out.append(merged)
    return out


def render(stage: str, *, sick: bool = False) -> list[str]:
    """Return the sprite as a list of terminal lines.

    Two source pixels stack into one terminal cell:
        top on,  bottom on  -> █
        top on,  bottom off -> ▀
        top off, bottom on  -> ▄
        top off, bottom off -> (space)

    Each output line is exactly as wide as the sprite (no padding).
    """
    bitmap = SPRITES.get(stage, SPRITES["egg"])
    if sick:
        bitmap = _overlay(bitmap, _SICK_OVERLAY)

    # Pair rows two at a time.
    lines: list[str] = []
    for i in range(0, len(bitmap), 2):
        top = bitmap[i]
        bottom = bitmap[i + 1] if i + 1 < len(bitmap) else "." * len(top)
        line_chars = []
        for t, b in zip(top, bottom):
            t_on = t == "#"
            b_on = b == "#"
            if t_on and b_on:
                line_chars.append("█")
            elif t_on:
                line_chars.append("▀")
            elif b_on:
                line_chars.append("▄")
            else:
                line_chars.append(" ")
        lines.append("".join(line_chars))
    return lines


def sprite_width(stage: str = "egg") -> int:
    """Visual width of a sprite (every cell is 1 column wide)."""
    return len(SPRITES.get(stage, SPRITES["egg"])[0])


def sprite_height(stage: str = "egg") -> int:
    """Rendered height (terminal lines) of a sprite."""
    return (len(SPRITES.get(stage, SPRITES["egg"])) + 1) // 2


__all__ = ["SPRITES", "render", "sprite_width", "sprite_height"]
