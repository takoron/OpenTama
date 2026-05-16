"""Persistent state for the OpenTama pet.

The state is serialized to JSON. By default it lives at
``~/.opentama/state.json``, but tests can override this via the
``OPENTAMA_STATE_PATH`` environment variable.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


# --- defaults ---------------------------------------------------------------

DEFAULT_HAPPINESS = 80.0
DEFAULT_HUNGER = 80.0
DEFAULT_ENERGY = 80.0


@dataclass
class TamaState:
    """The full persistent state for a Tamagotchi."""

    name: str = "Tama"
    company_ssid: str = ""

    # Stats range 0..100.
    happiness: float = DEFAULT_HAPPINESS
    hunger: float = DEFAULT_HUNGER  # 100 = full, 0 = starving
    energy: float = DEFAULT_ENERGY

    # Growth points accumulate while connected to the company SSID.
    growth_points: float = 0.0

    # Unix timestamps.
    born_at: float = 0.0
    last_tick_at: float = 0.0

    # Aggregate stats.
    total_office_seconds: float = 0.0
    days_at_office: int = 0

    # Achievement keys (e.g. "first_day", "hatched").
    achievements: list[str] = field(default_factory=list)

    alive: bool = True


# --- path resolution --------------------------------------------------------

_DEFAULT_DIR = Path.home() / ".opentama"
_DEFAULT_PATH = _DEFAULT_DIR / "state.json"


def get_state_path() -> Path:
    """Resolve the state-file path, honouring ``OPENTAMA_STATE_PATH``."""
    env = os.environ.get("OPENTAMA_STATE_PATH")
    if env:
        return Path(env)
    return _DEFAULT_PATH


# --- I/O --------------------------------------------------------------------


def load_state(path: Path | None = None) -> TamaState | None:
    """Load state from disk; return ``None`` if no state file exists."""
    p = path or get_state_path()
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Ignore unexpected keys gracefully (forward-compat).
    known = {f for f in TamaState.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known}
    return TamaState(**filtered)


def save_state(state: TamaState, path: Path | None = None) -> None:
    """Persist state to disk, creating the parent directory if needed."""
    p = path or get_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(asdict(state), fh, indent=2, ensure_ascii=False)
    # Atomic replace.
    tmp.replace(p)


def delete_state(path: Path | None = None) -> bool:
    """Remove the state file. Return True if a file was deleted."""
    p = path or get_state_path()
    if p.exists():
        p.unlink()
        return True
    return False
