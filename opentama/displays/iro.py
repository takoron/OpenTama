"""Iro — color mid-2000s flip-phone style frame."""

from __future__ import annotations

from .. import sprites
from ..plugins.api import StateView
from ._layout import vpad


LCD_WIDTH = 22


def _bar10(v: int) -> str:
    f = max(0, min(10, v // 10))
    return "#" * f + "." * (10 - f)


def _signal_bars(v: int) -> str:
    n = max(1, min(4, v // 25 + 1))
    return ("=" * n) + ("." * (4 - n))


def _is_sick(view: StateView) -> bool:
    return min(view.happiness, view.hunger, view.energy) <= 15


class IroDisplay:
    name = "iro"

    def render(self, view: StateView) -> str:
        sprite_lines = sprites.render(view.stage, sick=_is_sick(view))
        line = lambda s: "  |" + vpad(s, LCD_WIDTH) + "|"
        bar = "  +" + "-" * LCD_WIDTH + "+"
        sprite_rows = [line(f"     {row}") for row in sprite_lines]
        return "\n".join(
            [
                "  ." + "-" * LCD_WIDTH + ".",
                "  | (o)" + " " * (LCD_WIDTH - 7) + ".. |",
                bar,
                line(f" OpenTama  {_signal_bars(view.happiness)}  {view.energy:>3}%"),
                line(""),
                *sprite_rows,
                line(""),
                line(f" {view.name} ({view.stage},{view.growth_points}gp)"),
                line(f" happy  {_bar10(view.happiness)} {view.happiness:>3}"),
                line(f" hungry {_bar10(view.hunger)} {view.hunger:>3}"),
                line(f" energy {_bar10(view.energy)} {view.energy:>3}"),
                bar,
                line("   FEED   ^   MENU"),
                line("       < OK >"),
                line("   PLAY   v   BACK"),
                bar,
                line("  1 abc  2 def  3 ghi"),
                line("  4 jkl  5 mno  6 pqr"),
                line("  7 stu  8 vwx  9 yz"),
                line("   *      0      #"),
                "  '" + "-" * LCD_WIDTH + "'",
            ]
        )
