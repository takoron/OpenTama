"""Takoron (たころん) — OpenTama's takoyaki pet, in pixels.

Takoron is a takoyaki (たこ焼き) — a round ball of dough with octopus
inside, traditionally topped with sauce, green nori, and pickled
ginger, and crowned with a piece of dancing bonito flake.

Each stage is a 14×16 monochrome bitmap. Pixels are ``#`` (on) or
anything else (off). The :func:`render` function compresses two
vertical pixels into one terminal cell using the half-block
characters ``▀ ▄ █``, so each sprite renders as 14 cells wide × 8
lines tall — small enough to fit on a real ガラケー LCD.

Takoron's growth path:

* **egg**   — a plain dough ball, fresh out of the pan.
* **baby**  — face appears: closed ^_^ eyes, tiny smile.
* **child** — first topping dot lands.
* **teen**  — toppings scattered, a small bonito flake rises.
* **adult** — full Takoron: flake, all toppings, big smile, open mouth.
* **elder** — adult Takoron with extra steam wisps drifting up.

A ``sick`` overlay adds two sweat-drop pixels at the top corners.
"""

from __future__ import annotations


SPRITES: dict[str, list[str]] = {
    # ----- egg --------------------------------------------------------
    # plain dough ball, no face, no toppings.
    "egg": [
        "..............",
        "..............",
        ".....####.....",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".############.",
        ".############.",
        ".############.",
        ".############.",
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        ".....####.....",
    ],
    # ----- baby -------------------------------------------------------
    # face arrives: ^_^ closed eyes + a tiny smile.
    "baby": [
        "..............",
        "..............",
        ".....####.....",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".###.####.###.",  # ^_^ upper line (narrow gaps)
        ".##..####..##.",  # ^_^ lower line (wider gaps)
        ".############.",
        ".####.##.####.",  # tiny smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "..............",
    ],
    # ----- child ------------------------------------------------------
    # first sauce dot lands on the top.
    "child": [
        "..............",
        ".....####.....",
        "....######....",
        "...########...",
        "..##########..",
        ".####.#######.",  # one topping dot at col 5
        ".############.",
        ".###.####.###.",  # eye upper
        ".##..####..##.",  # eye lower
        ".############.",
        ".####.##.####.",  # smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "..............",
    ],
    # ----- teen -------------------------------------------------------
    # toppings scatter; a tiny bonito flake starts to dance.
    "teen": [
        ".........##...",  # flake top
        "........####..",  # flake body
        "......##.##...",  # flake meets ball
        "....########..",
        "...##########.",
        ".####.###.###.",  # 2 topping dots
        ".############.",
        ".###.####.###.",  # eye upper
        ".##..####..##.",  # eye lower
        ".############.",
        ".####.##.####.",  # smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "..............",
    ],
    # ----- adult ------------------------------------------------------
    # full Takoron: bonito flake on top, sauce + nori + ginger dots,
    # big closed-eye smile and an open mouth with the tongue showing.
    "adult": [
        "........##....",  # flake top
        ".......####...",  # flake body
        "......##.##...",  # flake base
        "....########..",  # ball top
        "...##########.",  # ball widens
        ".####.###.###.",  # topping row 1
        ".########.###.",  # topping row 2
        ".############.",  # cooked/face divider
        ".############.",  # face top
        ".###.####.###.",  # ^_^ eye upper
        ".##..####..##.",  # ^_^ eye lower
        ".############.",  # mid face
        ".####....####.",  # open smile (wide gap)
        ".######.######",  # tongue (mouth narrowing with tongue at col 7)
        "..##########..",  # ball bottom
        "...########...",  # rounded bottom
    ],
    # ----- elder ------------------------------------------------------
    # adult Takoron with extra steam puffs drifting up.
    "elder": [
        "...#....##....",  # steam puff + flake top
        ".#.....####...",  # more steam + flake
        "......##.##...",  # flake base
        "....########..",
        "...##########.",
        ".####.###.###.",  # toppings
        ".########.###.",
        ".############.",
        ".############.",
        ".###.####.###.",  # eyes (still ^_^, classic)
        ".##..####..##.",
        ".############.",
        ".####.##.####.",  # smaller, content smile
        ".#####..#####.",  # mouth narrows
        "..##########..",
        "...########...",
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
