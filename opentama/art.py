"""High-fidelity colour rendering of Takoron for truecolor terminals.

The compact monochrome sprites in :mod:`opentama.sprites` are what the
ガラケー display backends use. This module is the *accurate* portrait:
a per-pixel colour grid rendered with 24-bit ANSI escapes, using the
upper/lower half-block trick so each terminal cell carries two stacked
pixels (top = foreground colour, bottom = background colour).

Takoron is a takoyaki: a browned dough ball topped with green nori and
red pickled ginger, a pale bonito flake standing up at the top right,
and on the lower half a cream face with ^_^ closed eyes, pink cheeks,
and a little tongue. See ``CHARACTER.md`` for the character credit.

The art is composed from a base body plus overlays so the stages stay
consistent:

    egg   = base, face and toppings stripped (plain dough ball)
    baby  = base, toppings stripped, mouth closed
    child = base, mouth closed
    teen  = child + small flake
    adult = base + full flake (mouth open, tongue out)
    elder = adult + steam wisps

Colour key characters::

    .  transparent      D  dough (brown)     F  face (cream)
    o  body outline     g  green topping     r  red topping
    e  eye (dark)       c  cheek (pink)      m  mouth outline
    t  tongue (red)     k  flake             K  flake shadow
    j  flake outline    s  steam (elder)
"""

from __future__ import annotations

PALETTE: dict[str, tuple[int, int, int]] = {
    "o": (74, 48, 28),     # dark brown body outline
    "D": (201, 124, 51),   # browned dough
    "F": (247, 230, 205),  # cream face
    "g": (104, 159, 56),   # green nori
    "r": (201, 58, 48),    # red pickled ginger
    "e": (54, 36, 24),     # eyes
    "c": (242, 156, 158),  # pink cheeks
    "m": (120, 70, 50),    # mouth line
    "t": (224, 78, 78),    # tongue
    "w": (255, 255, 255),  # eye catchlight (white)
    "k": (238, 210, 132),  # bonito flake
    "K": (208, 170, 86),   # flake shadow
    "j": (150, 120, 60),   # flake outline
    "s": (200, 210, 215),  # steam
}

_WIDTH = 18


def _normalize(grid: list[str]) -> list[str]:
    out = []
    for row in grid:
        if len(row) < _WIDTH:
            row = row + "." * (_WIDTH - len(row))
        elif len(row) > _WIDTH:
            row = row[:_WIDTH]
        out.append(row)
    return out


# Base body: round takoyaki with toppings + face + ω mouth,
# but NO flake (the flake is overlaid per stage).
_BASE = _normalize([
    "..................",  # 0
    "..................",  # 1
    "......oooo........",  # 2  crown
    "....ooDDDDoo......",  # 3
    "..ooDDDDDDDDoo....",  # 4
    ".oDDgDDDDDrDDDo...",  # 5  green@4 red@9
    ".oDDDDDDDDDDDDo...",  # 6
    "oDDDDDrDDDgDDDDo..",  # 7  red@6 green@10
    "oDDDDDDDDDDDDDDo..",  # 8
    "oDgDDDDDDDDDDrDo..",  # 9  green@2 red@12
    "oFFFFFFFFFFFFFFo..",  # 10 face begins
    "oFFweeFFFFweeFFo..",  # 11 eyes top + white catchlight
    "oFFeeeFFFFeeeFFo..",  # 12 eyes middle (full round pupil)
    "oFFeeFFFFFFeeFFo..",  # 13 eyes bottom (rounded)
    "oFccFFFFFFFFccFo..",  # 14 cheeks
    "oFFFFFFFFFFFFFFo..",  # 15 face
    ".oFFFFmmmmFFFFo...",  # 16 open mouth — top lip (m, cols 6-9)
    ".oFFFFmttmFFFFo...",  # 17 open mouth — interior (tongue at 7,8)
    "..oFFFFFFFFFFo....",  # 18
    "...oooooooooo.....",  # 19 base outline
])

# ω mouth (おちょぼ口) — used for the baby stage only.
_OMEGA_MOUTH = _normalize([
    ".oFFFmFmFmFFFFo...",  # peaks  (m at cols 5,7,9)  -> row 16
    ".oFFFFmFmFFFFFo...",  # valleys (m at cols 6,8)   -> row 17
])


# Flake overlays (only the flake pixels; "." means "leave base alone").
_FLAKE_FULL = _normalize([
    "..............jj..",
    ".............jkKj.",
    "............jkkKj.",
    "...........jkkkj..",
    "..........jjkkj...",
    "...........jkj....",
])

_FLAKE_SMALL = _normalize([
    "..................",
    "..............jk..",
    ".............jkkj.",
    "............jkkj..",
])

_STEAM = _normalize([
    "..s...............",
    ".s.s..............",
    "..s...............",
])


def _replace(grid: list[str], mapping: dict[str, str]) -> list[str]:
    return ["".join(mapping.get(ch, ch) for ch in row) for row in grid]


def _overlay(base: list[str], over: list[str]) -> list[str]:
    out = list(base)
    for y, row in enumerate(over):
        if y >= len(out):
            break
        merged = list(out[y])
        for x, ch in enumerate(row):
            if ch != "." and x < len(merged):
                merged[x] = ch
        out[y] = "".join(merged)
    return out


def _strip_toppings(grid: list[str]) -> list[str]:
    return _replace(grid, {"g": "D", "r": "D"})


def _strip_face(grid: list[str]) -> list[str]:
    return _replace(grid, {"F": "D", "e": "D", "w": "D", "c": "D", "m": "D", "t": "D"})


def _set_mouth(grid: list[str], mouth: list[str], at: int = 16) -> list[str]:
    out = list(grid)
    for i, row in enumerate(mouth):
        if at + i < len(out):
            out[at + i] = row
    return out


def _build_stages() -> dict[str, list[str]]:
    base = _BASE  # eyes, cheeks, OPEN mouth (child / teen / adult / elder)
    child = base
    baby = _set_mouth(_strip_toppings(base), _OMEGA_MOUTH)  # ω only for baby
    egg = _strip_face(_strip_toppings(base))
    teen = _overlay(base, _FLAKE_SMALL)
    adult = _overlay(base, _FLAKE_FULL)
    elder = _overlay(adult, _STEAM)
    return {
        "egg": egg,
        "baby": baby,
        "child": child,
        "teen": teen,
        "adult": adult,
        "elder": elder,
    }


GRIDS: dict[str, list[str]] = _build_stages()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_RESET = "\x1b[0m"
_UPPER = "\u2580"  # ▀
_LOWER = "\u2584"  # ▄
_FULL = "\u2588"   # █


def _fg(rgb: tuple[int, int, int]) -> str:
    return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _bg(rgb: tuple[int, int, int]) -> str:
    return f"\x1b[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def render_color(stage: str) -> list[str]:
    """Render Takoron in 24-bit colour using half-block cells."""
    grid = GRIDS.get(stage, GRIDS["egg"])
    lines: list[str] = []
    for i in range(0, len(grid), 2):
        top = grid[i]
        bottom = grid[i + 1] if i + 1 < len(grid) else "." * len(top)
        cells: list[str] = []
        for t, b in zip(top, bottom):
            tc = PALETTE.get(t)
            bc = PALETTE.get(b)
            if tc and bc:
                cells.append(_fg(tc) + _bg(bc) + _UPPER + _RESET)
            elif tc:
                cells.append(_fg(tc) + _UPPER + _RESET)
            elif bc:
                cells.append(_fg(bc) + _LOWER + _RESET)
            else:
                cells.append(" ")
        lines.append("".join(cells))
    return lines


def render_mono(stage: str) -> list[str]:
    """Render the same grid in monochrome half-blocks (no colour)."""
    grid = GRIDS.get(stage, GRIDS["egg"])
    lines: list[str] = []
    for i in range(0, len(grid), 2):
        top = grid[i]
        bottom = grid[i + 1] if i + 1 < len(grid) else "." * len(top)
        cells = []
        for t, b in zip(top, bottom):
            t_on, b_on = t != ".", b != "."
            if t_on and b_on:
                cells.append(_FULL)
            elif t_on:
                cells.append(_UPPER)
            elif b_on:
                cells.append(_LOWER)
            else:
                cells.append(" ")
        lines.append("".join(cells))
    return lines


def supports_color(stream=None) -> bool:
    """Best-effort check for whether colour should be emitted."""
    import os
    import sys

    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


__all__ = ["GRIDS", "PALETTE", "render_color", "render_mono", "supports_color"]
