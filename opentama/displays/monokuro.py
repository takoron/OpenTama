"""Monokuro — monochrome early-90s feature-phone frame."""

from __future__ import annotations

from .. import sprites
from ..plugins.api import StateView
from ._layout import vpad


LCD_WIDTH = 18


def _bar7(v: int) -> str:
    f = max(0, min(7, v * 7 // 100))
    return "#" * f + "." * (7 - f)


def _is_sick(view: StateView) -> bool:
    return min(view.happiness, view.hunger, view.energy) <= 15


class MonokuroDisplay:
    name = "monokuro"

    def render(self, view: StateView) -> str:
        sprite_lines = sprites.render(view.stage, sick=_is_sick(view))
        line = lambda s: "  |" + vpad(s, LCD_WIDTH) + "|"
        bar = "  +" + "-" * LCD_WIDTH + "+"
        sprite_rows = [line(f"   {row}") for row in sprite_lines]
        return "\n".join(
            [
                "  " + " " * (LCD_WIDTH // 2 + 1) + "|",
                "  ." + "-" * LCD_WIDTH + ".",
                line(" : : : speaker : : "),
                bar,
                line(f" {view.name} ({view.stage})"),
                *sprite_rows,
                line(f" hp {_bar7(view.happiness)}"),
                line(f" fd {_bar7(view.hunger)}"),
                line(f" en {_bar7(view.energy)}"),
                bar,
                line("  1   2   3  ^"),
                line("  4   5   6  v"),
                line("  7   8   9 ENT"),
                line("  *   0   #"),
                "  '" + "-" * LCD_WIDTH + "'",
            ]
        )
