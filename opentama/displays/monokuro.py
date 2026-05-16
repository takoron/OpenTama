"""Monokuro — monochrome early-90s feature-phone frame."""

from __future__ import annotations

from ..plugins.api import StateView
from ._layout import vpad


_PET_ART = {
    "egg":   ["  ___  ", " /   \\ ", "| o o |", " \\___/ ", "       "],
    "baby":  [" ,---. ", "( o o )", " \\ ^ / ", "  ---  ", "       "],
    "child": [" .---. ", "( ^ ^ )", "/| v |\\", " `---' ", "       "],
    "teen":  [" .-=-. ", "( o.o )", "/|>_<|\\", " `---' ", "       "],
    "adult": [".-~~-. ", "( ^_^ )", "/|\\=/|\\", "d`---'b", "       "],
    "elder": [".-~~-. ", "( -.- )", "/|\\_/|\\", "d`---'b", "       "],
}


LCD_WIDTH = 18


def _bar7(v: int) -> str:
    f = max(0, min(7, v * 7 // 100))
    return "#" * f + "." * (7 - f)


class MonokuroDisplay:
    name = "monokuro"

    def render(self, view: StateView) -> str:
        art = _PET_ART.get(view.stage, _PET_ART["egg"])
        line = lambda s: "  |" + vpad(s, LCD_WIDTH) + "|"
        bar = "  +" + "-" * LCD_WIDTH + "+"
        return "\n".join(
            [
                "  " + " " * (LCD_WIDTH // 2 + 1) + "|",
                "  ." + "-" * LCD_WIDTH + ".",
                line(" : : : speaker : : "),
                bar,
                line(f" {view.name} ({view.stage})"),
                line(f"   {art[0]}"),
                line(f"   {art[1]}"),
                line(f"   {art[2]}"),
                line(f"   {art[3]}"),
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
