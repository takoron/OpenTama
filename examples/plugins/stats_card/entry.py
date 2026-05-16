"""Example display plugin: a one-line ASCII summary of the pet.

To install:
    1. Copy this directory to ~/.opentama/plugins/stats_card/
    2. Recompute the sha256:  python -m opentama plugin checksum entry.py
       → paste the result into plugin.toml's sha256 field.
    3. Trust it:               python -m opentama plugin trust ~/.opentama/plugins/stats_card
    4. Run:                    python -m opentama plugin run stats_card
"""

from opentama.plugins import DisplayPlugin


def _bar(value: int, width: int = 10) -> str:
    filled = max(0, min(width, value * width // 100))
    return "[" + "#" * filled + "." * (width - filled) + "]"


class StatsCard(DisplayPlugin):
    name = "stats_card"
    version = "0.1.0"

    def render(self, view) -> str:
        return (
            f"+----- {view.name} ({view.stage}, {view.growth_points}gp) -----+\n"
            f"| happy  {_bar(view.happiness)} {view.happiness:>3} |\n"
            f"| hungry {_bar(view.hunger)} {view.hunger:>3} |\n"
            f"| energy {_bar(view.energy)} {view.energy:>3} |\n"
            f"+--------------------------------+"
        )


PLUGIN = StatsCard()
