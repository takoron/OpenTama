"""Tests for the proximity (peer-sighting) module."""

from __future__ import annotations

from pathlib import Path

import pytest

from opentama.proximity import (
    Digest,
    LoopbackDetector,
    PeerEntry,
    PeerSighting,
    append_sighting,
    clear_log,
    format_digest,
    get_log_path,
    load_sightings,
    summarise,
)


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def log_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "proximity.jsonl"
    monkeypatch.setenv("OPENTAMA_PROXIMITY_LOG", str(p))
    return p


def _s(
    peer_id: str,
    detected_at: float,
    *,
    nickname: str | None = None,
    lang: str | None = None,
    rssi_bucket: str = "unknown",
) -> PeerSighting:
    return PeerSighting(
        peer_id=peer_id,
        nickname=nickname,
        lang=lang,
        rssi_bucket=rssi_bucket,
        detected_at=detected_at,
    )


# --- PeerSighting basics ----------------------------------------------------


def test_sighting_is_frozen():
    s = _s("a", 1.0)
    with pytest.raises((AttributeError, TypeError)):
        s.peer_id = "b"  # type: ignore[misc]


def test_sighting_defaults():
    s = PeerSighting(peer_id="abc")
    assert s.nickname is None
    assert s.lang is None
    assert s.rssi_bucket == "unknown"
    assert s.detected_at == 0.0


# --- get_log_path -----------------------------------------------------------


def test_log_path_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENTAMA_PROXIMITY_LOG", str(tmp_path / "foo.jsonl"))
    assert get_log_path() == tmp_path / "foo.jsonl"


def test_log_path_default_when_unset(monkeypatch):
    monkeypatch.delenv("OPENTAMA_PROXIMITY_LOG", raising=False)
    p = get_log_path()
    assert p.name == "proximity.jsonl"
    assert p.parent.name == ".opentama"


# --- append / load round-trip ----------------------------------------------


def test_append_then_load_roundtrip(log_path):
    a = _s("peer-a", 1000.0, nickname="アリス", rssi_bucket="near")
    b = _s("peer-b", 1100.0, lang="ja", rssi_bucket="close")
    append_sighting(a)
    append_sighting(b)
    out = load_sightings()
    assert out == [a, b]


def test_load_filters_by_since(log_path):
    append_sighting(_s("old", 1000.0))
    append_sighting(_s("recent", 2000.0))
    out = load_sightings(since=1500.0)
    assert [s.peer_id for s in out] == ["recent"]


def test_load_missing_log_returns_empty(log_path):
    assert not log_path.exists()
    assert load_sightings() == []


def test_load_skips_corrupt_lines(log_path):
    # First write valid + garbage + valid using the same writer the module uses.
    append_sighting(_s("good1", 100.0))
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write("\n")  # blank line
        fh.write('{"peer_id": 42}\n')  # wrong type — TypeError on dataclass
        fh.write('"a string, not an object"\n')  # not a dict
        fh.write('{"completely_unknown_key": true}\n')  # all keys filtered out -> PeerSighting()
    append_sighting(_s("good2", 200.0))
    ids = [s.peer_id for s in load_sightings()]
    assert "good1" in ids and "good2" in ids
    # The "all unknown keys" record degrades to a default PeerSighting
    # (peer_id=""). We tolerate it but make sure it didn't crash.
    assert all(isinstance(s, PeerSighting) for s in load_sightings())


def test_clear_log(log_path):
    append_sighting(_s("x", 1.0))
    assert log_path.exists()
    assert clear_log() is True
    assert not log_path.exists()
    assert clear_log() is False  # idempotent


# --- LoopbackDetector ------------------------------------------------------


def test_loopback_detector_drains_on_poll():
    d = LoopbackDetector()
    assert d.poll() == []
    d.push(_s("a", 1.0))
    d.push(_s("b", 2.0))
    out = d.poll()
    assert [s.peer_id for s in out] == ["a", "b"]
    assert d.poll() == []  # drained


# --- summarise --------------------------------------------------------------


def test_summarise_empty():
    d = summarise([])
    assert d.peer_count == 0
    assert d.total_sightings == 0
    assert d.peers == []


def test_summarise_single_peer():
    sightings = [
        _s("p", 100.0, nickname="ぺこ", lang="ja", rssi_bucket="far"),
        _s("p", 150.0, rssi_bucket="near"),
        _s("p", 200.0, rssi_bucket="close"),
    ]
    d = summarise(sightings)
    assert d.peer_count == 1
    e = d.peers[0]
    assert e.peer_id == "p"
    assert e.nickname == "ぺこ"
    assert e.lang == "ja"
    assert e.sightings == 3
    assert e.first_seen_at == 100.0
    assert e.last_seen_at == 200.0
    # closest_bucket should converge on the closest seen.
    assert e.closest_bucket == "close"
    assert d.window_start == 100.0
    assert d.window_end == 200.0


def test_summarise_multi_peer_sort_by_sightings_then_first_seen():
    sightings = [
        _s("a", 100.0),
        _s("b", 110.0),
        _s("b", 120.0),
        _s("c", 130.0),
        _s("c", 140.0),
        _s("c", 150.0),
    ]
    d = summarise(sightings)
    # c (3 sightings) first, then b (2), then a (1).
    assert [p.peer_id for p in d.peers] == ["c", "b", "a"]


def test_summarise_window_filter():
    sightings = [
        _s("old", 100.0),
        _s("mid", 200.0),
        _s("recent", 300.0),
    ]
    d = summarise(sightings, window_start=150.0, window_end=250.0)
    assert [p.peer_id for p in d.peers] == ["mid"]
    assert d.window_start == 150.0
    assert d.window_end == 250.0


def test_summarise_bucket_priority_keeps_closest():
    # Even if "far" arrives last, "close" is the recorded closest.
    sightings = [
        _s("p", 100.0, rssi_bucket="close"),
        _s("p", 200.0, rssi_bucket="far"),
    ]
    d = summarise(sightings)
    assert d.peers[0].closest_bucket == "close"


def test_summarise_inherits_metadata_from_first_non_null():
    # First sighting has no nickname; second supplies one.
    sightings = [
        _s("p", 100.0),
        _s("p", 200.0, nickname="late-name", lang="en"),
    ]
    d = summarise(sightings)
    e = d.peers[0]
    assert e.nickname == "late-name"
    assert e.lang == "en"


# --- format_digest ---------------------------------------------------------


def test_format_digest_empty():
    d = Digest(window_start=0.0, window_end=0.0, peers=[])
    out = format_digest(d)
    assert "ありません" in out


def test_format_digest_lists_each_peer():
    digest = summarise(
        [
            _s("a", 100.0, nickname="アリス", rssi_bucket="close"),
            _s("a", 110.0, rssi_bucket="near"),
            _s("b", 120.0, lang="ja", rssi_bucket="far"),
        ]
    )
    out = format_digest(digest)
    assert "2 人とすれ違いました" in out
    assert "アリス" in out
    assert "[ja]" in out  # b has lang but no nickname → peer_id shown + lang tag
    assert "closest: close" in out
    assert "closest: far" in out


def test_format_digest_falls_back_to_peer_id_when_no_nickname():
    digest = summarise([_s("anon-peer-id-xyz", 100.0)])
    out = format_digest(digest)
    assert "anon-peer-id-xyz" in out


# --- IRProximityDetector ---------------------------------------------------


from opentama.ir.protocol import Frame, FrameType, encode
from opentama.ir.transport import LoopbackIRTransport
from opentama.proximity import IRProximityDetector


def _drain(detector: IRProximityDetector, attempts: int = 8) -> list[PeerSighting]:
    """Poll until no more sightings come back, or attempts exhausted."""
    out: list[PeerSighting] = []
    for _ in range(attempts):
        chunk = detector.poll(timeout=0.05)
        if not chunk:
            # Give the loopback one more chance — but bail on the
            # *second* empty poll to avoid hanging if nothing ever
            # arrives.
            chunk2 = detector.poll(timeout=0.05)
            if not chunk2:
                break
            out.extend(chunk2)
        else:
            out.extend(chunk)
    return out


def test_ir_detector_hello_to_sighting():
    a, b = LoopbackIRTransport.pair()
    b.send(
        encode(
            Frame.of(
                FrameType.HELLO,
                {"name": "アリス", "stage": "child", "gp": 60},
            )
        )
    )
    detector = IRProximityDetector(
        a, rssi_bucket="close", clock=lambda: 100.0
    )
    sightings = _drain(detector)
    assert len(sightings) == 1
    s = sightings[0]
    assert s.peer_id == "アリス"
    assert s.nickname == "アリス"
    assert s.rssi_bucket == "close"
    assert s.detected_at == 100.0


def test_ir_detector_empty_transport_returns_no_sightings():
    a, _ = LoopbackIRTransport.pair()
    detector = IRProximityDetector(a)
    assert detector.poll(timeout=0.05) == []


def test_ir_detector_multiple_frames_in_one_stream():
    a, b = LoopbackIRTransport.pair()
    b.send(encode(Frame.of(FrameType.HELLO, {"name": "alice"})))
    b.send(encode(Frame.of(FrameType.HELLO, {"name": "bob"})))
    detector = IRProximityDetector(a, clock=lambda: 200.0)
    names = sorted(s.peer_id for s in _drain(detector))
    assert names == ["alice", "bob"]


def test_ir_detector_recognises_gift_and_visit():
    a, b = LoopbackIRTransport.pair()
    b.send(encode(Frame.of(FrameType.GIFT, {"kind": "food", "from": "bob"})))
    b.send(encode(Frame.of(FrameType.VISIT, {"from": "carol"})))
    detector = IRProximityDetector(a)
    names = sorted(s.peer_id for s in _drain(detector))
    assert names == ["bob", "carol"]


def test_ir_detector_ignores_ack():
    a, b = LoopbackIRTransport.pair()
    b.send(encode(Frame.of(FrameType.ACK, {"thanks": "bob"})))
    detector = IRProximityDetector(a)
    # ACK carries no peer identifier we trust — should be silently dropped.
    assert _drain(detector) == []


def test_ir_detector_resyncs_past_garbage():
    a, b = LoopbackIRTransport.pair()
    # Garbage prefix, then a valid HELLO.
    b.send(b"\x00\xff\x01\x02\x03")
    b.send(encode(Frame.of(FrameType.HELLO, {"name": "dora"})))
    detector = IRProximityDetector(a)
    sightings = _drain(detector)
    assert [s.peer_id for s in sightings] == ["dora"]


def test_ir_detector_uses_specified_rssi_bucket():
    a, b = LoopbackIRTransport.pair()
    b.send(encode(Frame.of(FrameType.HELLO, {"name": "elise"})))
    detector = IRProximityDetector(a, rssi_bucket="near")
    sightings = _drain(detector)
    assert sightings and sightings[0].rssi_bucket == "near"


def test_ir_detector_drops_hello_without_name():
    a, b = LoopbackIRTransport.pair()
    b.send(encode(Frame.of(FrameType.HELLO, {})))  # no name → no peer id
    detector = IRProximityDetector(a)
    assert _drain(detector) == []


def test_ir_detector_end_to_end_with_session_initiator():
    """A real Session.greet() on B should appear as a sighting on A's detector.

    This verifies that the detector tolerates the actual on-the-wire
    output of the existing greet() initiator, not just hand-crafted
    HELLO frames.
    """
    from opentama.core import Tamagotchi
    from opentama.ir.session import Session
    from opentama.state import TamaState

    a, b = LoopbackIRTransport.pair()
    detector = IRProximityDetector(a)
    # B is the initiator pet.
    b_state = TamaState(
        name="フランク",
        company_ssid="OfficeWiFi",
        last_tick_at=1.0,
    )
    b_tama = Tamagotchi(b_state, ssid_provider=lambda: "OfficeWiFi", clock=lambda: 1.0)
    b_session = Session(b_tama, b, timeout=0.2)
    # greet() will send a HELLO and then try to read a reply (which we
    # don't bother sending — we only care that A sees the HELLO).
    b_session.greet()
    sightings = _drain(detector)
    assert any(s.peer_id == "フランク" for s in sightings)
