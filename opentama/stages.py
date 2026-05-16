"""Life stages for OpenTama.

The pixel-art bitmap for each stage lives in :mod:`opentama.sprites`;
this module is the source of truth for stage *thresholds* and exposes
the rendered art string as :attr:`Stage.art` for the default status
output.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import sprites


@dataclass(frozen=True)
class Stage:
    """A single life stage."""

    name: str
    min_growth: int

    @property
    def art(self) -> str:
        """Pixel-art rendering of this stage (multi-line string)."""
        return "\n".join(sprites.render(self.name))


# Stages in increasing growth order.
STAGES: tuple[Stage, ...] = (
    Stage("egg", 0),
    Stage("baby", 10),
    Stage("child", 50),
    Stage("teen", 200),
    Stage("adult", 500),
    Stage("elder", 1500),
)


def stage_for(growth_points: int) -> Stage:
    """Return the stage corresponding to the given growth points."""
    current = STAGES[0]
    for stage in STAGES:
        if growth_points >= stage.min_growth:
            current = stage
        else:
            break
    return current
