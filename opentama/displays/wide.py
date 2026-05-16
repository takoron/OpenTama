"""Wide — late-era widescreen feature phone."""

from __future__ import annotations

from ..plugins.api import StateView
from ._layout import vpad


_PET_ART = {
    "egg":   ["    ___    ", "   /   \\   ", "  | o o |  ", "   \\___/   "],
    "baby":  ["   ,---.   ", "  ( o o )  ", "   \\ ^ /   ", "    ---    "],
    "child": ["   .---.   ", "  ( ^ ^ )  ", "  /| v |\\  ", "   `---'   "],
    "teen":  ["   .-=-.   ", "  ( o.o )  ", "  /|>_<|\\  ", "   `---'   "],
    "adult": ["  .-~~-.   ", "  ( ^_^ )  ", "  /|\\=/|\\  ", "  d`---'b  "],
    "elder": ["  .-~~-.   ", "  ( -.- )  ", "  /|\\_/|\\  ", "  d`---'b  "],
}


LCD_WIDTH = 28


def _bar12(v: int) -> str:
    f = max(0, min(12, v * 12 // 100))
    return "#" * f + "." * (12 - f)


def _mood(view: StateView) -> str:
    if min(view.happiness, view.hunger, view.energy) <= 15:
        return ":("
    if view.happiness >= 80:
        return ":D"
    if view.happiness >= 40:
        return ":)"
    return ":/"


class WideDisplay:
    name = "wide"

    def render(self, view: StateView) -> str:
        art = _PET_ART.get(view.stage, _PET_ART["egg"])
        line = lambda s: "  |" + vpad(s, LCD_WIDTH) + "|"
        bar = "  +" + "-" * LCD_WIDTH + "+"
        topbar = f"{_mood(view)}  {view.name}  .  {view.stage}  .  {view.growth_points}gp"
        return "\n".join(
            [
                bar,
                line(" .                       ()"),
                bar,
                line(f" {topbar}"),
                line(""),
                line(art[0]),
                line(art[1]),
                line(art[2]),
                line(art[3]),
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
