"""OpenTama IR wire protocol.

Frame layout (big-endian throughout):

    +---------+---------+--------+------------------+---------+--------+
    | magic   | version | type   | payload length   | payload | crc16  |
    | 2 bytes | 1 byte  | 1 byte | 2 bytes (uint16) | N bytes | 2 bytes|
    +---------+---------+--------+------------------+---------+--------+

The CRC-16/CCITT-FALSE (poly=0x1021, init=0xFFFF) is computed over
magic..payload (i.e. every byte before the CRC itself).
"""

from __future__ import annotations

import enum
import json
import struct
from dataclasses import dataclass

MAGIC = b"OT"
VERSION = 1
MAX_PAYLOAD = 1024  # 1 KB is plenty for a tama greeting

HEADER_FMT = ">2sBBH"  # magic, version, type, payload_len
HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 6
CRC_SIZE = 2


class FrameType(enum.IntEnum):
    HELLO = 1   # introduce self
    STATE = 2   # share a stats snapshot
    GIFT = 3    # send a small gift to a peer
    VISIT = 4   # mutual happiness exchange
    ACK = 5     # acknowledgement


@dataclass(frozen=True)
class Frame:
    type: FrameType
    payload: bytes = b""

    # --- JSON helpers (frames carry small JSON payloads) ------------------
    @classmethod
    def of(cls, type_: FrameType, obj: dict | None = None) -> "Frame":
        payload = b"" if obj is None else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_PAYLOAD:
            raise ValueError(f"payload too large: {len(payload)} > {MAX_PAYLOAD}")
        return cls(type_, payload)

    def json(self) -> dict:
        if not self.payload:
            return {}
        return json.loads(self.payload.decode("utf-8"))


# ---------------------------------------------------------------------------
# CRC-16/CCITT-FALSE
# ---------------------------------------------------------------------------


def crc16(data: bytes, init: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE."""
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# encode / decode
# ---------------------------------------------------------------------------


class FrameError(Exception):
    """Base for malformed-frame errors."""


class BadMagic(FrameError):
    pass


class BadVersion(FrameError):
    pass


class BadCRC(FrameError):
    pass


class BadLength(FrameError):
    pass


def encode(frame: Frame) -> bytes:
    if len(frame.payload) > MAX_PAYLOAD:
        raise ValueError("payload exceeds MAX_PAYLOAD")
    header = struct.pack(HEADER_FMT, MAGIC, VERSION, int(frame.type), len(frame.payload))
    body = header + frame.payload
    return body + struct.pack(">H", crc16(body))


def decode(buf: bytes) -> Frame:
    if len(buf) < HEADER_SIZE + CRC_SIZE:
        raise BadLength(f"buffer too short: {len(buf)}")
    magic, version, type_, plen = struct.unpack(HEADER_FMT, buf[:HEADER_SIZE])
    if magic != MAGIC:
        raise BadMagic(f"bad magic: {magic!r}")
    if version != VERSION:
        raise BadVersion(f"unsupported version: {version}")
    expected_total = HEADER_SIZE + plen + CRC_SIZE
    if len(buf) != expected_total:
        raise BadLength(f"expected {expected_total} bytes, got {len(buf)}")
    payload = buf[HEADER_SIZE : HEADER_SIZE + plen]
    received_crc = struct.unpack(">H", buf[-CRC_SIZE:])[0]
    if received_crc != crc16(buf[:-CRC_SIZE]):
        raise BadCRC("CRC mismatch")
    try:
        ftype = FrameType(type_)
    except ValueError as e:
        raise FrameError(f"unknown frame type: {type_}") from e
    return Frame(ftype, payload)


def parse_stream(buf: bytes) -> tuple[list[Frame], bytes]:
    """Parse zero or more frames from a buffer; return (frames, leftover).

    Useful for streaming IR ingestion where multiple frames may be present.
    """
    frames: list[Frame] = []
    cursor = 0
    while cursor < len(buf):
        # Resync to magic.
        idx = buf.find(MAGIC, cursor)
        if idx < 0:
            cursor = len(buf)
            break
        if len(buf) - idx < HEADER_SIZE:
            break
        _, _, _, plen = struct.unpack(HEADER_FMT, buf[idx : idx + HEADER_SIZE])
        total = HEADER_SIZE + plen + CRC_SIZE
        if len(buf) - idx < total:
            break
        chunk = buf[idx : idx + total]
        try:
            frames.append(decode(chunk))
        except FrameError:
            # Skip past this magic and resync.
            cursor = idx + 1
            continue
        cursor = idx + total
    return frames, buf[cursor:]
