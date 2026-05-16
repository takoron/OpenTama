"""High-level IR conversations between two Tamagotchis.

This is where two pets actually *do* things to each other:

* :meth:`Session.greet`  — exchange names/stages with a peer, get a
                           small happiness bump for the meeting.
* :meth:`Session.gift`   — send a small food/toy gift to a peer; the
                           receiver's :class:`Tamagotchi` records it.
* :meth:`Session.visit`  — full visit: greet → exchange state → mutual
                           happiness bonus.

All methods are symmetric: one side calls the active method (e.g.
``greet``), the other side calls :meth:`Session.serve_once` to handle
whatever arrives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core import Tamagotchi
from .protocol import Frame, FrameType, decode, encode
from .transport import IRTransport


GIFT_HUNGER_DELTA = 15.0
GIFT_HAPPINESS_DELTA = 5.0
GREET_HAPPINESS_DELTA = 8.0
VISIT_HAPPINESS_DELTA = 12.0


@dataclass
class PeerInfo:
    name: str
    stage: str
    growth_points: int


@dataclass
class SessionResult:
    """What happened during a session call."""

    peer: Optional[PeerInfo] = None
    received: Optional[Frame] = None
    sent: Optional[Frame] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


class Session:
    """A stateful conversation over a transport, on behalf of one pet."""

    def __init__(self, tama: Tamagotchi, transport: IRTransport, *, timeout: float = 2.0):
        self.tama = tama
        self.transport = transport
        self.timeout = timeout

    # --- helpers ----------------------------------------------------------

    def _send(self, frame: Frame) -> None:
        self.transport.send(encode(frame))

    def _recv_one(self) -> Optional[Frame]:
        raw = self.transport.recv(timeout=self.timeout)
        if not raw:
            return None
        try:
            return decode(raw)
        except Exception:  # noqa: BLE001 — surface protocol errors as None
            return None

    def _self_hello_payload(self) -> dict:
        s = self.tama.state
        return {
            "name": s.name,
            "stage": self.tama.stage.name,
            "gp": int(s.growth_points),
        }

    # --- active operations ------------------------------------------------

    def greet(self) -> SessionResult:
        """Initiator side of a greeting handshake."""
        hello = Frame.of(FrameType.HELLO, self._self_hello_payload())
        self._send(hello)
        reply = self._recv_one()
        if reply is None:
            return SessionResult(error="no response", sent=hello)
        if reply.type != FrameType.HELLO:
            return SessionResult(error=f"unexpected reply: {reply.type.name}", sent=hello, received=reply)
        peer_info = _parse_hello(reply)
        self.tama.state.happiness = _clamp(self.tama.state.happiness + GREET_HAPPINESS_DELTA)
        _record_friend(self.tama, peer_info.name, "greet")
        return SessionResult(peer=peer_info, received=reply, sent=hello)

    def gift(self, kind: str = "food") -> SessionResult:
        """Send a gift; expect an ACK."""
        if kind not in {"food", "toy"}:
            raise ValueError(f"unknown gift kind: {kind!r}")
        payload = {"kind": kind, "from": self.tama.state.name}
        gift_frame = Frame.of(FrameType.GIFT, payload)
        self._send(gift_frame)
        reply = self._recv_one()
        if reply is None:
            return SessionResult(error="no ack", sent=gift_frame)
        if reply.type != FrameType.ACK:
            return SessionResult(error=f"unexpected reply: {reply.type.name}", sent=gift_frame, received=reply)
        return SessionResult(received=reply, sent=gift_frame)

    def visit(self) -> SessionResult:
        """Full visit: greet then mutual happiness boost."""
        g = self.greet()
        if not g.ok:
            return g
        visit_frame = Frame.of(FrameType.VISIT, {"from": self.tama.state.name})
        self._send(visit_frame)
        reply = self._recv_one()
        if reply is None:
            return SessionResult(error="visit not acked", sent=visit_frame, peer=g.peer)
        if reply.type != FrameType.ACK:
            return SessionResult(error=f"unexpected reply: {reply.type.name}", sent=visit_frame, received=reply, peer=g.peer)
        self.tama.state.happiness = _clamp(self.tama.state.happiness + VISIT_HAPPINESS_DELTA)
        _record_friend(self.tama, g.peer.name, "visit")
        return SessionResult(peer=g.peer, received=reply, sent=visit_frame)

    # --- passive (responder) ---------------------------------------------

    def serve_once(self) -> SessionResult:
        """Process a single inbound frame and react.

        Call this from the "other" pet's process. Returns a description
        of what happened.
        """
        incoming = self._recv_one()
        if incoming is None:
            return SessionResult(error="no inbound frame")

        if incoming.type == FrameType.HELLO:
            peer = _parse_hello(incoming)
            reply = Frame.of(FrameType.HELLO, self._self_hello_payload())
            self._send(reply)
            self.tama.state.happiness = _clamp(self.tama.state.happiness + GREET_HAPPINESS_DELTA)
            _record_friend(self.tama, peer.name, "greet")
            return SessionResult(peer=peer, received=incoming, sent=reply)

        if incoming.type == FrameType.GIFT:
            data = incoming.json()
            kind = data.get("kind", "food")
            from_name = data.get("from", "?")
            self._apply_gift(kind)
            ack = Frame.of(FrameType.ACK, {"thanks": from_name})
            self._send(ack)
            return SessionResult(received=incoming, sent=ack, peer=PeerInfo(from_name, "?", 0))

        if incoming.type == FrameType.VISIT:
            data = incoming.json()
            from_name = data.get("from", "?")
            self.tama.state.happiness = _clamp(self.tama.state.happiness + VISIT_HAPPINESS_DELTA)
            _record_friend(self.tama, from_name, "visit")
            ack = Frame.of(FrameType.ACK)
            self._send(ack)
            return SessionResult(received=incoming, sent=ack, peer=PeerInfo(from_name, "?", 0))

        return SessionResult(error=f"unsupported frame type: {incoming.type.name}", received=incoming)

    # --- internals --------------------------------------------------------

    def _apply_gift(self, kind: str) -> None:
        self.tama.state.hunger = _clamp(self.tama.state.hunger + GIFT_HUNGER_DELTA)
        self.tama.state.happiness = _clamp(self.tama.state.happiness + GIFT_HAPPINESS_DELTA)
        if kind == "toy":
            self.tama.state.happiness = _clamp(self.tama.state.happiness + GIFT_HAPPINESS_DELTA)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _parse_hello(frame: Frame) -> PeerInfo:
    j = frame.json()
    return PeerInfo(
        name=str(j.get("name", "?")),
        stage=str(j.get("stage", "?")),
        growth_points=int(j.get("gp", 0)),
    )


def _record_friend(tama: Tamagotchi, peer_name: str, kind: str) -> None:
    """Record that we met someone, as an achievement-style marker."""
    key = f"met:{peer_name}"
    if key not in tama.state.achievements:
        tama.state.achievements.append(key)
    if kind == "visit":
        v_key = f"visited:{peer_name}"
        if v_key not in tama.state.achievements:
            tama.state.achievements.append(v_key)
