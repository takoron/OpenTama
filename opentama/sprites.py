"""Takoron (たころん) — OpenTama's cute octopus pet, in pixels.

Each stage is a 14×16 monochrome bitmap. Pixels are ``#`` (on) or
anything else (off). The :func:`render` function compresses two
vertical pixels into one terminal cell using the half-block
characters ``▀ ▄ █``, so each sprite renders as 14 cells wide × 8
lines tall — small enough to fit on a real ガラケー LCD.

Takoron's growth path:

* **egg**   — smooth shell with sleepy ^^ closed eyes and a smile.
* **baby**  — head only, two big eyes, tiny stub legs.
* **child** — fuller head, four short tentacles.
* **teen**  — bigger body, wavier tentacles, wider smile.
* **adult** — round face, dimpled cheeks, four flowing tentacles.
* **elder** — adult Takoron with a magnificent mustache.

A ``sick`` overlay adds two sweat-drop pixels at the top corners.

Reading the bitmap source:
  * a fully-solid body row is ``.############.`` (12-wide head, padded
    to 14)
  * an eye row uses ``.##..####..##.`` — head edges, 2-wide eye
    whites at cols 3–4 and 9–10, head bridge in the middle.
  * tentacle rows alternate ``.##.##..##.##.`` (centered, 4 stubs)
    and offset variants to suggest motion.
"""

from __future__ import annotations


SPRITES: dict[str, list[str]] = {
    # ----- egg ----------------------------------------------------------
    "egg": [
        "..............",
        ".....####.....",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".############.",
        ".##..####..##.",  # sleepy ^^ closed eyes
        ".############.",
        ".############.",
        ".####.##.####.",  # tiny smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        ".....####.....",
    ],
    # ----- baby ---------------------------------------------------------
    "baby": [
        "..............",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".##..####..##.",  # big eye row 1
        ".##..####..##.",  # big eye row 2
        ".############.",
        ".####.##.####.",  # small mouth
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "....##..##....",  # two stub legs
        "....##..##....",
        "..............",
    ],
    # ----- child --------------------------------------------------------
    "child": [
        "..............",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".##..####..##.",  # eyes
        ".##..####..##.",
        ".############.",
        ".####.##.####.",  # small smile
        ".############.",
        "..##########..",
        "...########...",
        ".##.##..##.##.",  # 4 tentacle stubs
        ".##.##..##.##.",
        ".##.##..##.##.",
        "..............",
    ],
    # ----- teen ---------------------------------------------------------
    "teen": [
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        "##############",
        "###..####..###",  # eye row 1
        "###..####..###",  # eye row 2
        "##############",
        "##.########.##",  # cheek dimples
        "###.######.###",  # smile
        "##############",
        ".############.",
        ".##.##..##.##.",  # tentacles wave left
        ".##.##..##.##.",
        "..##.##.##.##.",  # tentacles wave right
        "..##.##.##.##.",
    ],
    # ----- adult --------------------------------------------------------
    "adult": [
        "....######....",
        "..##########..",
        ".############.",
        "##############",
        "###..####..###",  # eye row 1
        "###..####..###",  # eye row 2
        "##############",
        "##.########.##",  # cheek dimples
        "###.######.###",  # smile upper
        "####.####.####",  # smile lower
        ".############.",
        ".##.##..##.##.",  # 4 tentacles
        ".##.##..##.##.",
        ".##.##..##.##.",
        "..##.##.##.##.",  # tail end waves
        "..##.##.##.##.",
    ],
    # ----- elder --------------------------------------------------------
    "elder": [
        "....######....",
        "..##########..",
        ".############.",
        "##.########.##",  # bushy eyebrows
        "##############",
        "###..####..###",  # eyes
        "###..####..###",
        "##############",
        "####.####.####",  # mustache top curl
        "###.######.###",  # mustache middle
        "##.########.##",  # mustache tips
        ".############.",
        ".##.##..##.##.",
        ".##.##..##.##.",
        "..##.##.##.##.",
        "..##.##.##.##.",
    ],
}


# Width sanity check at import time.
for _name, _rows in SPRITES.items():
    _w = len(_rows[0])
    for _i, _row in enumerate(_rows):
        if len(_row) != _w:
            raise AssertionError(
                f"sprite {_name!r} row {_i} is {len(_row)} chars, expected {_w}"
            )
del _name, _rows, _w, _i, _row


# Sweat-drop overlay used when the pet's stats drop too low.
_SICK_OVERLAY = [
    "#............#",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
    "..............",
]


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
    """Render Takoron at ``stage`` as a list of terminal lines.

    Two source pixels stack into one terminal cell via half-blocks
    ``▀ ▄ █`` (and space).
    """
    bitmap = SPRITES.get(stage, SPRITES["egg"])
    if sick:
        bitmap = _overlay(bitmap, _SICK_OVERLAY)

    lines: list[str] = []
    for i in range(0, len(bitmap), 2):
        top = bitmap[i]
        bottom = bitmap[i + 1] if i + 1 < len(bitmap) else "." * len(top)
        chars = []
        for t, b in zip(top, bottom):
            t_on, b_on = t == "#", b == "#"
            if t_on and b_on:
                chars.append("█")
            elif t_on:
                chars.append("▀")
            elif b_on:
                chars.append("▄")
            else:
                chars.append(" ")
        lines.append("".join(chars))
    return lines


def sprite_width(stage: str = "egg") -> int:
    return len(SPRITES.get(stage, SPRITES["egg"])[0])


def sprite_height(stage: str = "egg") -> int:
    return (len(SPRITES.get(stage, SPRITES["egg"])) + 1) // 2


__all__ = ["SPRITES", "render", "sprite_width", "sprite_height"]
