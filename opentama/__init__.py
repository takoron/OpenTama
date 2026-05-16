"""OpenTama — a Claude Code skill that grows a Tamagotchi when you come to the office.

Subpackages:
  * :mod:`opentama.ir`        — IR protocol, transport, session
  * :mod:`opentama.plugins`   — capability-based plugin loader
  * :mod:`opentama.displays`  — retro feature-phone display backends
"""

from .core import Tamagotchi, TickResult
from .stages import STAGES, Stage, stage_for
from .state import TamaState, load_state, save_state

__all__ = [
    "Tamagotchi",
    "TickResult",
    "STAGES",
    "Stage",
    "stage_for",
    "TamaState",
    "load_state",
    "save_state",
]

__version__ = "0.2.0"
