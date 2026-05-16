"""Display backends — render the pet inside a retro feature-phone frame.

Each backend takes a :class:`StateView` (or a Tamagotchi via
:func:`render_with_tama`) and returns a multi-line string. The
``DISPLAYS`` registry maps a short name → instance, so the CLI can
choose by ``--display=monokuro``.
"""

from __future__ import annotations

from typing import Protocol

from ..plugins.api import StateView
from .iro import IroDisplay
from .monokuro import MonokuroDisplay
from .wide import WideDisplay


class Display(Protocol):
    name: str

    def render(self, view: StateView) -> str: ...


DISPLAYS: dict[str, Display] = {
    "monokuro": MonokuroDisplay(),
    "iro": IroDisplay(),
    "wide": WideDisplay(),
}


def get(name: str) -> Display:
    if name not in DISPLAYS:
        raise KeyError(f"unknown display: {name!r}. Try: {', '.join(DISPLAYS)}")
    return DISPLAYS[name]


def render_with_tama(display_name: str, tama) -> str:
    """Convenience: render the given Tamagotchi via the named display."""
    s = tama.state
    view = StateView(
        name=s.name,
        stage=tama.stage.name,
        growth_points=int(s.growth_points),
        happiness=int(s.happiness),
        hunger=int(s.hunger),
        energy=int(s.energy),
    )
    return get(display_name).render(view)


__all__ = ["DISPLAYS", "Display", "get", "render_with_tama"]
