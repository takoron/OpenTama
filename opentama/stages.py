"""Life stages for OpenTama and their ASCII art representations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    """A single life stage."""

    name: str
    min_growth: int
    art: str


EGG_ART = r"""
   ___
  /   \
 | ° ° |
  \___/
""".strip("\n")

BABY_ART = r"""
   ,---.
  ( o o )
   \ ^ /
    ---
""".strip("\n")

CHILD_ART = r"""
   .---.
  ( ^ ^ )
  /| v |\
   `---'
""".strip("\n")

TEEN_ART = r"""
   .-=-.
  ( o.o )
  /|>_<|\
   `---'
""".strip("\n")

ADULT_ART = r"""
   .-~~-.
  ( ^ω^ )
  /|\=/|\
  d`---'b
""".strip("\n")

ELDER_ART = r"""
   .-~~-.
  ( -.- )🥢
  /|\_/|\
  d`---'b
""".strip("\n")


# Stages in increasing growth order.
STAGES: tuple[Stage, ...] = (
    Stage("egg", 0, EGG_ART),
    Stage("baby", 10, BABY_ART),
    Stage("child", 50, CHILD_ART),
    Stage("teen", 200, TEEN_ART),
    Stage("adult", 500, ADULT_ART),
    Stage("elder", 1500, ELDER_ART),
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
