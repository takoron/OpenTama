"""Tests for IR transports."""

import threading
import time

import pytest

from opentama.ir.transport import (
    LoopbackIRTransport,
    SerialIRTransport,
    open_transport,
)


# --- Loopback ---------------------------------------------------------------


def test_loopback_pair_can_round_trip():
    a, b = LoopbackIRTransport.pair()
    a.send(b"hello")
    assert b.recv(timeout=0.5) == b"hello"


def test_loopback_recv_times_out_when_idle():
    a, _b = LoopbackIRTransport.pair()
    start = time.monotonic()
    out = a.recv(timeout=0.05)
    elapsed = time.monotonic() - start
    assert out == b""
    assert 0.04 <= elapsed < 0.5


def test_loopback_two_way_independent():
    a, b = LoopbackIRTransport.pair()
    a.send(b"a-to-b")
    b.send(b"b-to-a")
    assert b.recv(timeout=0.2) == b"a-to-b"
    assert a.recv(timeout=0.2) == b"b-to-a"


def test_loopback_concurrent_send_then_recv():
    a, b = LoopbackIRTransport.pair()
    received: list[bytes] = []

    def reader():
        received.append(b.recv(timeout=1.0))

    t = threading.Thread(target=reader)
    t.start()
    time.sleep(0.05)  # ensure reader is parked
    a.send(b"hi")
    t.join(timeout=2.0)
    assert received == [b"hi"]


def test_loopback_close_makes_recv_return_empty():
    a, b = LoopbackIRTransport.pair()
    a.close()
    b.close()
    assert a.recv(timeout=0.1) == b""


# --- SerialIRTransport with a fake serial ----------------------------------


class FakeSerial:
    def __init__(self):
        self.written = bytearray()
        self.read_buffer = bytearray()
        self.flushed = 0
        self.closed = False

    def write(self, data):
        self.written.extend(data)

    def read(self, n):
        if not self.read_buffer:
            return b""
        take = min(n, len(self.read_buffer))
        out = bytes(self.read_buffer[:take])
        del self.read_buffer[:take]
        return out

    def flush(self):
        self.flushed += 1

    def close(self):
        self.closed = True


def test_serial_transport_writes_and_flushes():
    fake = FakeSerial()
    t = SerialIRTransport("DUMMY", serial_factory=lambda p, b: fake)
    t.send(b"payload")
    assert bytes(fake.written) == b"payload"
    assert fake.flushed >= 1


def test_serial_transport_receives_within_timeout():
    fake = FakeSerial()
    fake.read_buffer.extend(b"hello")
    t = SerialIRTransport("DUMMY", serial_factory=lambda p, b: fake)
    assert t.recv(n=5, timeout=0.5) == b"hello"


def test_serial_transport_returns_empty_on_timeout():
    fake = FakeSerial()
    t = SerialIRTransport("DUMMY", serial_factory=lambda p, b: fake)
    assert t.recv(n=4, timeout=0.05) == b""


def test_serial_transport_close_closes_serial():
    fake = FakeSerial()
    t = SerialIRTransport("DUMMY", serial_factory=lambda p, b: fake)
    t.close()
    assert fake.closed is True


# --- factory ---------------------------------------------------------------


def test_open_transport_rejects_unknown_uri():
    with pytest.raises(ValueError):
        open_transport("ftp://nope")


def test_open_transport_loopback_uri():
    t = open_transport("loopback://")
    assert isinstance(t, LoopbackIRTransport)
