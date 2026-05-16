"""OpenTama plugin API.

A plugin is a Python module shipped in a directory containing:

    <plugin>/
      plugin.toml      (manifest: name, version, capabilities, sha256)
      <entrypoint>.py  (module with a top-level ``PLUGIN`` instance)

Plugins are *not* fully sandboxed — Python doesn't make that easy — but
the API they're given (:class:`PluginContext`) only exposes the data
and operations they declared in their manifest under
``capabilities``. Combined with manifest integrity checks (SHA-256) and
an explicit trust store, this is enough to learn safely from
third-party plugins without giving them free rein over your pet.

Threat model (and where this stops):
  * Defends against: bit-rot, accidental tampering, plugins that try
    to do more than they declared (e.g. a display plugin trying to
    drive the IR transport).
  * Does NOT defend against: a malicious plugin you've explicitly
    trusted that decides to ``import os`` and read your home
    directory. For that you'd need OS-level sandboxing (subprocess +
    seccomp / wasm / etc.) which is out of scope.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class Capability(str, enum.Enum):
    IR_TRANSMIT = "ir.transmit"
    IR_RECEIVE = "ir.receive"
    DISPLAY = "display"
    STATE_READ = "state.read"
    STATE_WRITE = "state.write"

    @classmethod
    def parse(cls, value: str) -> "Capability":
        try:
            return cls(value)
        except ValueError as e:
            raise ValueError(f"unknown capability: {value!r}") from e


class CapabilityDenied(PermissionError):
    """Raised when a plugin uses an API it didn't declare."""


# ---------------------------------------------------------------------------
# State view (read-only by default)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateView:
    """A read-only snapshot of the pet's public state."""

    name: str
    stage: str
    growth_points: int
    happiness: int
    hunger: int
    energy: int


def _snapshot(tama) -> StateView:
    s = tama.state
    return StateView(
        name=s.name,
        stage=tama.stage.name,
        growth_points=int(s.growth_points),
        happiness=int(s.happiness),
        hunger=int(s.hunger),
        energy=int(s.energy),
    )


# ---------------------------------------------------------------------------
# PluginContext: the only API surface plugins get
# ---------------------------------------------------------------------------


class PluginContext:
    """Whitelisted access for plugins.

    Each method checks the corresponding :class:`Capability` and raises
    :class:`CapabilityDenied` if missing. Plugins should hold on to
    this object and call through it for everything that touches the
    host pet.
    """

    def __init__(
        self,
        capabilities: set[Capability],
        tama=None,
        ir_send: Optional[Callable[[bytes], None]] = None,
        ir_recv: Optional[Callable[[float], bytes]] = None,
    ):
        self._caps = set(capabilities)
        self._tama = tama
        self._ir_send = ir_send
        self._ir_recv = ir_recv

    # --- introspection ----------------------------------------------------

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(self._caps)

    def has(self, cap: Capability) -> bool:
        return cap in self._caps

    # --- state ------------------------------------------------------------

    def get_state(self) -> StateView:
        self._require(Capability.STATE_READ)
        if self._tama is None:
            raise RuntimeError("no tamagotchi attached to context")
        return _snapshot(self._tama)

    def feed(self) -> None:
        self._require(Capability.STATE_WRITE)
        self._tama.feed()

    def play(self) -> None:
        self._require(Capability.STATE_WRITE)
        self._tama.play()

    # --- IR ---------------------------------------------------------------

    def ir_send(self, frame_bytes: bytes) -> None:
        self._require(Capability.IR_TRANSMIT)
        if self._ir_send is None:
            raise RuntimeError("no IR transport bound to this context")
        self._ir_send(frame_bytes)

    def ir_recv(self, timeout: float = 1.0) -> bytes:
        self._require(Capability.IR_RECEIVE)
        if self._ir_recv is None:
            raise RuntimeError("no IR transport bound to this context")
        return self._ir_recv(timeout)

    # --- internals --------------------------------------------------------

    def _require(self, cap: Capability) -> None:
        if cap not in self._caps:
            raise CapabilityDenied(f"missing capability: {cap.value}")


# ---------------------------------------------------------------------------
# Plugin base classes
# ---------------------------------------------------------------------------


class Plugin(ABC):
    """Base class for all plugins."""

    #: Plugin identity. Must match the manifest.
    name: str = ""
    version: str = "0.0.0"

    def on_load(self, ctx: PluginContext) -> None:
        """Hook called once after the plugin is verified and loaded."""

    @abstractmethod
    def run(self, ctx: PluginContext) -> Any:
        """Entry point for the plugin's main action."""


class DisplayPlugin(Plugin):
    """A plugin that renders the pet's state as a string."""

    def run(self, ctx: PluginContext) -> Any:  # default just renders
        return self.render(ctx.get_state())

    @abstractmethod
    def render(self, view: StateView) -> str:
        """Return the rendered display."""
