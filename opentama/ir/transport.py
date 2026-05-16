"""IR transport implementations.

A transport just moves bytes between two endpoints. The protocol layer
sits on top and provides framing.

Two implementations:

* :class:`SerialIRTransport` — talks to a USB-attached IR adapter that
  exposes a serial-port interface (the common case for cheap IrDA-USB
  adapters and home-brew Arduino IR bridges).
* :class:`LoopbackIRTransport` — paired in-memory transport for tests
  and demos. Two endpoints share two ``deque`` queues swapped at each
  end so "send" on one becomes "recv" on the other.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional


class IRTransport(ABC):
    """A byte-level IR transport."""

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Push bytes onto the wire."""

    @abstractmethod
    def recv(self, n: int = 4096, timeout: float = 1.0) -> bytes:
        """Pull up to ``n`` bytes within ``timeout`` seconds (empty on miss)."""

    def close(self) -> None:
        """Optional cleanup; default no-op."""


# ---------------------------------------------------------------------------
# Loopback (for tests)
# ---------------------------------------------------------------------------


class LoopbackIRTransport(IRTransport):
    """In-memory transport. Use :meth:`pair` to get two ends."""

    def __init__(self, outbound: deque, inbound: deque, lock: threading.Lock) -> None:
        self._out = outbound
        self._in = inbound
        self._lock = lock
        self._closed = False

    @classmethod
    def pair(cls) -> tuple["LoopbackIRTransport", "LoopbackIRTransport"]:
        """Return two transports that talk to each other."""
        a_to_b: deque = deque()
        b_to_a: deque = deque()
        lock = threading.Lock()
        a = cls(outbound=a_to_b, inbound=b_to_a, lock=lock)
        b = cls(outbound=b_to_a, inbound=a_to_b, lock=lock)
        return a, b

    def send(self, data: bytes) -> None:
        if self._closed:
            raise RuntimeError("transport closed")
        with self._lock:
            self._out.extend(data)

    def recv(self, n: int = 4096, timeout: float = 1.0) -> bytes:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                if self._in:
                    take = min(n, len(self._in))
                    out = bytes(self._in.popleft() for _ in range(take))
                    return out
                if self._closed:
                    return b""
            if time.monotonic() >= deadline:
                return b""
            time.sleep(0.005)

    def close(self) -> None:
        self._closed = True


# ---------------------------------------------------------------------------
# USB serial IR adapter
# ---------------------------------------------------------------------------


class SerialIRTransport(IRTransport):
    """Talks to a USB-attached IR adapter through pyserial.

    pyserial is only imported lazily so the rest of OpenTama works on
    machines that don't have it installed.
    """

    DEFAULT_BAUDRATE = 9600

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        *,
        serial_factory=None,
    ) -> None:
        if serial_factory is None:
            try:
                import serial  # type: ignore
            except ImportError as e:  # pragma: no cover - exercised only when pyserial missing
                raise RuntimeError(
                    "pyserial is required for SerialIRTransport. "
                    "Install it with `pip install pyserial`."
                ) from e

            def serial_factory(p: str, b: int):
                return serial.Serial(p, b, timeout=0.1)

        self._ser = serial_factory(port, baudrate)

    def send(self, data: bytes) -> None:
        self._ser.write(data)
        flush = getattr(self._ser, "flush", None)
        if callable(flush):
            flush()

    def recv(self, n: int = 4096, timeout: float = 1.0) -> bytes:
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline and len(buf) < n:
            chunk = self._ser.read(n - len(buf))
            if not chunk:
                # Small idle wait; the underlying serial timeout is already short.
                continue
            buf.extend(chunk)
            # If we got something, return it eagerly — frames are tiny.
            break
        return bytes(buf)

    def close(self) -> None:
        close = getattr(self._ser, "close", None)
        if callable(close):
            close()


# ---------------------------------------------------------------------------
# Factory by URI string (used by the CLI)
# ---------------------------------------------------------------------------


def open_transport(uri: str) -> IRTransport:
    """Open a transport from a URI string.

    Supported:
      * ``serial:///dev/ttyUSB0`` — USB serial IR adapter
      * ``serial:///dev/ttyUSB0?baud=19200``
      * ``loopback://``           — pair via :meth:`LoopbackIRTransport.pair`
                                     (rarely useful through this entry point;
                                     mostly here for symmetry)
    """
    if uri.startswith("serial://"):
        rest = uri[len("serial://") :]
        if "?" in rest:
            port, _, qs = rest.partition("?")
            baud = SerialIRTransport.DEFAULT_BAUDRATE
            for part in qs.split("&"):
                if part.startswith("baud="):
                    baud = int(part[len("baud=") :])
            return SerialIRTransport(port, baud)
        return SerialIRTransport(rest)
    if uri.startswith("loopback://"):
        a, _ = LoopbackIRTransport.pair()
        return a
    raise ValueError(f"unknown transport URI: {uri!r}")
