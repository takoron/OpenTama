"""Tests for the ガラケー (feature phone) IrDA vObject interop."""

from __future__ import annotations

import pytest

from opentama.garake import (
    VObject,
    parse_vobject,
    parse_vobject_stream,
    sightings_from_irda_blob,
    vobject_to_sighting,
)
from opentama.ir.transport import LoopbackIRTransport
from opentama.proximity import IrDAProximityDetector, PeerSighting


# --- fixtures ---------------------------------------------------------------


VCARD_ALICE = (
    "BEGIN:VCARD\r\n"
    "VERSION:2.1\r\n"
    "FN:アリス\r\n"
    "N:Suzuki;Alice;;;\r\n"
    "NICKNAME:アリスさん\r\n"
    "TEL;CELL:090-1234-5678\r\n"
    "EMAIL:alice@example.com\r\n"
    "END:VCARD\r\n"
)

VCARD_BOB_FN_ONLY = (
    "BEGIN:VCARD\r\n"
    "VERSION:2.1\r\n"
    "FN:ボブ\r\n"
    "END:VCARD\r\n"
)

VCARD_N_ONLY = (
    "BEGIN:VCARD\r\n"
    "VERSION:2.1\r\n"
    "N:Tanaka;Hiroshi;;;\r\n"
    "END:VCARD\r\n"
)

VNOTE_MEMO = (
    "BEGIN:VNOTE\r\n"
    "VERSION:1.1\r\n"
    "BODY;CHARSET=UTF-8:たころん\r\n"
    "END:VNOTE\r\n"
)


# --- parse_vobject ----------------------------------------------------------


def test_parse_vcard_basic():
    v = parse_vobject(VCARD_ALICE)
    assert v is not None
    assert v.kind == "VCARD"
    assert v.fields["FN"] == "アリス"
    assert v.fields["NICKNAME"] == "アリスさん"
    # Parameter stripped from key.
    assert v.fields["TEL"] == "090-1234-5678"
    assert v.fields["EMAIL"] == "alice@example.com"


def test_parse_vnote_strips_param_from_key():
    v = parse_vobject(VNOTE_MEMO)
    assert v is not None
    assert v.kind == "VNOTE"
    # "BODY;CHARSET=UTF-8" → key "BODY"
    assert v.fields["BODY"] == "たころん"


def test_parse_vobject_returns_none_on_garbage():
    assert parse_vobject("hello world") is None
    assert parse_vobject("") is None
    assert parse_vobject("BEGIN:VCARD\nFN:nope\n") is None  # no END


def test_parse_vobject_case_insensitive_begin_end():
    text = "begin:vcard\r\nFN:lower\r\nend:vcard\r\n"
    v = parse_vobject(text)
    assert v is not None and v.kind == "VCARD"
    assert v.fields["FN"] == "lower"


def test_parse_vobject_handles_line_folding():
    # RFC 2425 line folding: continuation lines start with whitespace.
    text = (
        "BEGIN:VCARD\r\n"
        "FN:Very Long\r\n"
        " Name Continued\r\n"
        "END:VCARD\r\n"
    )
    v = parse_vobject(text)
    assert v is not None
    assert v.fields["FN"] == "Very LongName Continued"


def test_parse_vobject_first_occurrence_wins():
    # Phones sometimes emit duplicate keys; we keep the first.
    text = (
        "BEGIN:VCARD\r\n"
        "FN:First\r\n"
        "FN:Second\r\n"
        "END:VCARD\r\n"
    )
    v = parse_vobject(text)
    assert v is not None
    assert v.fields["FN"] == "First"


# --- parse_vobject_stream --------------------------------------------------


def test_stream_extracts_multiple_vobjects():
    blob = (VCARD_ALICE + "\r\n" + VCARD_BOB_FN_ONLY).encode("utf-8")
    out = parse_vobject_stream(blob)
    assert [v.kind for v in out] == ["VCARD", "VCARD"]
    assert out[0].fields["FN"] == "アリス"
    assert out[1].fields["FN"] == "ボブ"


def test_stream_tolerates_leading_and_trailing_garbage():
    blob = (
        b"\x00\x00garbage prefix\xff"
        + VCARD_ALICE.encode("utf-8")
        + b"\x00trailing\xff"
    )
    out = parse_vobject_stream(blob)
    assert len(out) == 1
    assert out[0].fields["FN"] == "アリス"


def test_stream_decodes_shift_jis():
    blob = VCARD_ALICE.encode("shift_jis")
    out = parse_vobject_stream(blob)
    assert len(out) == 1
    assert out[0].fields["FN"] == "アリス"


def test_stream_handles_vcard_and_vnote_mixed():
    blob = (VCARD_BOB_FN_ONLY + VNOTE_MEMO).encode("utf-8")
    out = parse_vobject_stream(blob)
    kinds = [v.kind for v in out]
    assert kinds == ["VCARD", "VNOTE"]
    assert out[1].fields["BODY"] == "たころん"


def test_stream_returns_empty_when_no_vobject():
    assert parse_vobject_stream(b"nothing here at all") == []


# --- vobject_to_sighting ---------------------------------------------------


def _v(kind, **fields):
    return VObject(kind=kind, fields=fields, raw="")


def test_vcard_fn_becomes_peer_id():
    s = vobject_to_sighting(
        _v("VCARD", FN="アリス", NICKNAME="アリスさん"),
        clock=lambda: 100.0,
    )
    assert s is not None
    assert s.peer_id == "アリス"
    assert s.nickname == "アリスさん"
    assert s.detected_at == 100.0
    assert s.rssi_bucket == "close"


def test_vcard_falls_back_to_n_then_nickname():
    s_n = vobject_to_sighting(_v("VCARD", N="Tanaka;Hiroshi;;;"), clock=lambda: 0)
    assert s_n is not None and s_n.peer_id == "Tanaka Hiroshi"

    s_nick = vobject_to_sighting(_v("VCARD", NICKNAME="Just Nickname"), clock=lambda: 0)
    assert s_nick is not None and s_nick.peer_id == "Just Nickname"


def test_vcard_with_no_identifiers_returns_none():
    assert vobject_to_sighting(_v("VCARD", TEL="090-1234")) is None


def test_vcard_nickname_equal_to_fn_does_not_double():
    s = vobject_to_sighting(_v("VCARD", FN="Same", NICKNAME="Same"))
    assert s is not None
    assert s.peer_id == "Same"
    assert s.nickname == "Same"


def test_vnote_body_becomes_peer_id():
    s = vobject_to_sighting(_v("VNOTE", BODY="たころん"), clock=lambda: 100.0)
    assert s is not None
    assert s.peer_id == "たころん"
    assert s.nickname == "たころん"


def test_vnote_without_body_returns_none():
    assert vobject_to_sighting(_v("VNOTE")) is None


def test_vcalendar_returns_none():
    # We deliberately don't try to invent identifiers for non-card types.
    assert vobject_to_sighting(_v("VCALENDAR", SUMMARY="meeting")) is None


def test_rssi_bucket_can_be_overridden():
    s = vobject_to_sighting(
        _v("VCARD", FN="x"), rssi_bucket="near", clock=lambda: 0
    )
    assert s is not None and s.rssi_bucket == "near"


# --- sightings_from_irda_blob ----------------------------------------------


def test_sightings_from_blob_round_trip():
    blob = (VCARD_ALICE + VNOTE_MEMO).encode("utf-8")
    out = sightings_from_irda_blob(blob, clock=lambda: 200.0)
    assert len(out) == 2
    assert {s.peer_id for s in out} == {"アリス", "たころん"}
    assert all(s.detected_at == 200.0 for s in out)


def test_sightings_from_blob_skips_unmappable():
    bad_vcard = (
        "BEGIN:VCARD\r\n"
        "TEL:090-9999\r\n"
        "END:VCARD\r\n"
    )
    blob = (bad_vcard + VCARD_BOB_FN_ONLY).encode("utf-8")
    out = sightings_from_irda_blob(blob)
    assert [s.peer_id for s in out] == ["ボブ"]


# --- IrDAProximityDetector --------------------------------------------------


def _drain(detector: IrDAProximityDetector, attempts: int = 8) -> list[PeerSighting]:
    out: list[PeerSighting] = []
    for _ in range(attempts):
        chunk = detector.poll(timeout=0.05)
        if not chunk:
            chunk2 = detector.poll(timeout=0.05)
            if not chunk2:
                break
            out.extend(chunk2)
        else:
            out.extend(chunk)
    return out


def test_irda_detector_emits_sighting_for_vcard():
    a, b = LoopbackIRTransport.pair()
    b.send(VCARD_ALICE.encode("utf-8"))
    detector = IrDAProximityDetector(a, clock=lambda: 100.0)
    sightings = _drain(detector)
    assert len(sightings) == 1
    assert sightings[0].peer_id == "アリス"
    assert sightings[0].rssi_bucket == "close"
    assert sightings[0].detected_at == 100.0


def test_irda_detector_handles_two_back_to_back_vcards():
    a, b = LoopbackIRTransport.pair()
    b.send((VCARD_BOB_FN_ONLY + VCARD_ALICE).encode("utf-8"))
    detector = IrDAProximityDetector(a)
    sightings = _drain(detector)
    assert sorted(s.peer_id for s in sightings) == ["アリス", "ボブ"]


def test_irda_detector_empty_when_no_vobject():
    a, _ = LoopbackIRTransport.pair()
    detector = IrDAProximityDetector(a)
    assert detector.poll(timeout=0.05) == []


def test_irda_detector_skips_partial_vobject():
    """A truncated vCard should be buffered, then matched once completed."""
    a, b = LoopbackIRTransport.pair()
    head = b"BEGIN:VCARD\r\nFN:Stream\r\n"
    tail = b"END:VCARD\r\n"
    detector = IrDAProximityDetector(a, clock=lambda: 50.0)

    b.send(head)
    # First poll: only head — no END yet.
    assert detector.poll(timeout=0.05) == []
    b.send(tail)
    sightings = _drain(detector)
    assert len(sightings) == 1 and sightings[0].peer_id == "Stream"


def test_irda_detector_buffer_trim_keeps_recent_vobject():
    """A burst of garbage longer than the buffer cap shouldn't lose a trailing vCard."""
    a, b = LoopbackIRTransport.pair()
    detector = IrDAProximityDetector(
        a, max_buffer_bytes=512, clock=lambda: 0.0
    )
    # Send way more garbage than the cap, then a clean vCard.
    b.send(b"\x00" * 2048)
    b.send(VCARD_BOB_FN_ONLY.encode("utf-8"))
    sightings = _drain(detector)
    assert sightings and sightings[0].peer_id == "ボブ"


def test_irda_detector_decodes_shift_jis_send():
    a, b = LoopbackIRTransport.pair()
    b.send(VCARD_ALICE.encode("shift_jis"))
    detector = IrDAProximityDetector(a)
    sightings = _drain(detector)
    assert sightings and sightings[0].peer_id == "アリス"
