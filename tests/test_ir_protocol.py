"""Tests for the IR wire protocol."""

import pytest

from opentama.ir.protocol import (
    HEADER_SIZE,
    MAGIC,
    VERSION,
    BadCRC,
    BadLength,
    BadMagic,
    BadVersion,
    Frame,
    FrameError,
    FrameType,
    crc16,
    decode,
    encode,
    parse_stream,
)


# --- CRC --------------------------------------------------------------------


def test_crc16_known_vector():
    # CRC-16/CCITT-FALSE("123456789") == 0x29B1
    assert crc16(b"123456789") == 0x29B1


def test_crc16_empty_is_initial_value():
    assert crc16(b"") == 0xFFFF


def test_crc16_changes_on_each_byte():
    a = crc16(b"hello")
    b = crc16(b"hellp")
    assert a != b


# --- round-trip -------------------------------------------------------------


def test_roundtrip_empty_payload():
    f = Frame(FrameType.ACK, b"")
    assert decode(encode(f)) == f


def test_roundtrip_json_payload():
    f = Frame.of(FrameType.HELLO, {"name": "Tama", "stage": "baby", "gp": 12})
    out = decode(encode(f))
    assert out.type is FrameType.HELLO
    assert out.json() == {"name": "Tama", "stage": "baby", "gp": 12}


def test_japanese_payload_roundtrip():
    f = Frame.of(FrameType.GIFT, {"from": "たまお", "kind": "food"})
    out = decode(encode(f))
    assert out.json()["from"] == "たまお"


# --- malformed frames -------------------------------------------------------


def test_decode_rejects_short_buffer():
    with pytest.raises(BadLength):
        decode(b"")


def test_decode_rejects_bad_magic():
    bad = b"XX" + encode(Frame(FrameType.ACK))[2:]
    with pytest.raises(BadMagic):
        decode(bad)


def test_decode_rejects_bad_version():
    raw = bytearray(encode(Frame(FrameType.ACK)))
    raw[2] = 99  # version byte
    # Re-CRC so we don't trip the CRC check first.
    from opentama.ir.protocol import CRC_SIZE
    body = bytes(raw[:-CRC_SIZE])
    new_crc = crc16(body).to_bytes(2, "big")
    with pytest.raises(BadVersion):
        decode(body + new_crc)


def test_decode_rejects_bad_crc():
    raw = bytearray(encode(Frame.of(FrameType.HELLO, {"x": 1})))
    raw[-1] ^= 0xFF
    with pytest.raises(BadCRC):
        decode(bytes(raw))


def test_decode_rejects_unknown_frame_type():
    from opentama.ir.protocol import CRC_SIZE

    raw = bytearray(encode(Frame(FrameType.ACK)))
    raw[3] = 99
    body = bytes(raw[:-CRC_SIZE])
    new_crc = crc16(body).to_bytes(2, "big")
    with pytest.raises(FrameError):
        decode(body + new_crc)


def test_decode_rejects_length_mismatch():
    raw = encode(Frame.of(FrameType.HELLO, {"x": 1}))
    with pytest.raises(BadLength):
        decode(raw + b"\x00")
    with pytest.raises(BadLength):
        decode(raw[:-1])


def test_max_payload_enforced():
    # Build a payload that's deliberately too big.
    huge = {"k": "x" * 2000}
    with pytest.raises(ValueError):
        Frame.of(FrameType.STATE, huge)


# --- stream parsing ---------------------------------------------------------


def test_parse_stream_two_frames():
    f1 = encode(Frame.of(FrameType.HELLO, {"n": 1}))
    f2 = encode(Frame.of(FrameType.ACK))
    frames, rest = parse_stream(f1 + f2)
    assert [fr.type for fr in frames] == [FrameType.HELLO, FrameType.ACK]
    assert rest == b""


def test_parse_stream_handles_garbage_prefix():
    f1 = encode(Frame.of(FrameType.HELLO, {"n": 1}))
    frames, rest = parse_stream(b"GARBAGE" + f1)
    assert len(frames) == 1
    assert frames[0].json() == {"n": 1}
    assert rest == b""


def test_parse_stream_keeps_partial_tail():
    f1 = encode(Frame.of(FrameType.HELLO, {"n": 1}))
    partial = f1[:-1]
    frames, rest = parse_stream(partial)
    assert frames == []
    assert rest == partial
