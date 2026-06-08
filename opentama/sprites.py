"""Takoron (タコロン) — OpenTama's takoyaki pet, in pixels.

Takoron is a takoyaki (たこ焼き) — a round ball of dough with octopus
inside, traditionally topped with sauce, green nori, and pickled
ginger, and crowned with a piece of dancing bonito flake. The
character was created by the original author of this project; see
``CHARACTER.md`` for the full credit and reference.

Each stage is a 14×16 monochrome bitmap. Pixels are ``#`` (on) or
anything else (off). The :func:`render` function compresses two
vertical pixels into one terminal cell using the half-block
characters ``▀ ▄ █``, so each sprite renders as 14 cells wide × 8
lines tall — small enough to fit on a real ガラケー LCD.

Takoron's growth path:

* **egg**   — plain dough ball fresh from the pan.
* **baby**  — face appears: closed ^_^ eyes, small smile, cheek dimples.
* **child** — first topping dot lands on the dough.
* **teen**  — toppings scatter; a small bonito flake starts to dance.
* **adult** — full Takoron: flake, all toppings, open smile with tongue.
* **elder** — *Takoron-no-Ohsama* (たころんの王さま): the elder form
  earns a three-spiked crown. The dancing bonito-flake step from
  earlier stages settles into a king's diadem; the toppings stay,
  the cheek dimples stay, the smile stays — only the headdress
  changes.

A ``sick`` overlay adds two sweat-drop pixels at the top corners.

Reading the bitmap source:
  ``.############.``   12-wide solid body row
  ``.##.######.##.``   row with cheek dimples (1-wide gaps at cols 3, 10)
  ``.###.####.###.``   row with closed-eye tops (^_^ peaks)
  ``.##..####..##.``   row with closed-eye bottoms (^_^ spread)
  ``.####....####.``   open mouth (4-wide center gap)
  ``.######.######``   tongue-suggestion row (single ON pixel below
                       a wider mouth opening)
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
    # face arrives: ^_^ closed eyes, cheek dimples, tiny smile.
    "baby": [
        "..............",
        "..............",
        ".....####.....",
        "....######....",
        "...########...",
        "..##########..",
        ".############.",
        ".###.####.###.",  # ^_^ peaks
        ".##..####..##.",  # ^_^ spread
        ".##.######.##.",  # cheek dimples
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
        ".##.######.##.",  # cheek dimples
        ".####.##.####.",  # small smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "..............",
    ],
    # ----- teen -------------------------------------------------------
    # toppings scatter, the bonito flake begins to dance.
    "teen": [
        "........##....",  # flake top
        ".......####...",  # flake body
        "......##.##...",  # flake meets ball
        "....########..",
        "...##########.",
        ".####.###.###.",  # 2 topping dots
        ".############.",
        ".###.####.###.",  # eye upper
        ".##..####..##.",  # eye lower
        ".##.######.##.",  # cheek dimples
        ".####.##.####.",  # smile
        ".############.",
        "..##########..",
        "...########...",
        "....######....",
        "..............",
    ],
    # ----- adult ------------------------------------------------------
    # full Takoron: bonito flake on top, scattered toppings, big closed-
    # eye smile, cheek dimples, and an open mouth with the tongue.
    "adult": [
        "........##....",  # flake top
        ".......####...",  # flake body
        "......##.##...",  # flake base
        "....########..",  # ball top
        "...##########.",  # ball widens
        ".####.###.###.",  # topping row 1
        ".#######.####.",  # topping row 2
        ".############.",  # cooked-dough / face divider
        ".###.####.###.",  # ^_^ eye upper
        ".##..####..##.",  # ^_^ eye lower
        ".##.######.##.",  # cheek dimples
        ".############.",  # mid face
        ".####....####.",  # open mouth (4-wide)
        ".######.######",  # tongue (mouth narrows; tongue at col 7)
        "..##########..",
        "...########...",
    ],
    # ----- elder ------------------------------------------------------
    # たころんの王さま — faithful to the project owner's reference
    # illustration: three tall pointed crown spikes, a wide two-row
    # crown band with a clear gap above the takoyaki, scattered 青のり
    # dots on the upper half, two round dot eyes (not the ^_^ form
    # used by younger stages), and a small content smile.
    "elder": [
        "..#...##...#..",  # crown spike tips (3 peaks: cols 2, 6-7, 11)
        ".###.####.###.",  # crown spike bodies, widening
        ".############.",  # crown band (upper)
        ".############.",  # crown band (lower)
        "..##########..",  # ball top curve — small visual gap below crown
        ".############.",  # ball widens
        ".####.###.###.",  # 青のり dots, scattered (row 1)
        ".##.######.##.",  # 青のり dots, scattered (row 2)
        ".############.",  # cooked-dough divider
        "...##....##...",  # round dot eyes (left + right) — distinct from ^_^
        ".############.",  # face mid-band
        ".####.##.####.",  # small content smile
        ".############.",  # body
        "..##########..",  # ball bottom curve
        "...########...",
        "....######....",
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
