"""Wide — late-era widescreen feature phone."""

from __future__ import annotations

from .. import sprites
from ..plugins.api import StateView
from ._layout import vpad


LCD_WIDTH = 28


def _bar12(v: int) -> str:
    f = max(0, min(12, v * 12 // 100))
    return "#" * f + "." * (12 - f)


def _is_sick(view: StateView) -> bool:
    return min(view.happiness, view.hunger, view.energy) <= 15


def _mood(view: StateView) -> str:
    if _is_sick(view):
        return ":("
    if view.happiness >= 80:
        return ":D"
    if view.happiness >= 40:
        return ":)"
    return ":/"


class WideDisplay:
    name = "wide"

    def render(self, view: StateView) -> str:
        sprite_lines = sprites.render(view.stage, sick=_is_sick(view))
        line = lambda s: "  |" + vpad(s, LCD_WIDTH) + "|"
        bar = "  +" + "-" * LCD_WIDTH + "+"
        topbar = f"{_mood(view)} {view.name} {view.stage} {view.growth_points}gp"
        sprite_rows = [line(f"        {row}") for row in sprite_lines]
        return "\n".join(
            [
                bar,
                line(" .                       ()"),
                bar,
                line(f" {topbar}"),
                line(""),
                *sprite_rows,
                line(""),
                line(f" happy   {_bar12(view.happiness)} {view.happiness:>3}"),
                line(f" hungry  {_bar12(view.hunger)} {view.hunger:>3}"),
                line(f" energy  {_bar12(view.energy)} {view.energy:>3}"),
                bar,
                line("  feed  play  sleep  ir  cfg"),
                bar,
                line("  [ < ]  [ OK ]   [ > ]"),
                bar,
            ]
        )
