"""Byte-level parity between the M5StickC firmware encoder and the Python one.

`firmware/m5stickc/src/opentama_proto.cpp` is a hand port of
`opentama/ir/protocol.py:encode`. The two implementations must produce
the same bytes for the same inputs — otherwise the PC running
`proximity scan` won't recognise frames coming from the stick.

We can't run C++ from this test suite, but we can:
  1. Lock the Python encoder's output to a specific hex string for the
     default firmware HELLO payload (`platformio.ini`'s
     `OPENTAMA_PET_NAME` / `STAGE` / `GP` constants). Any change to the
     Python encoder, the CRC, or the JSON payload format trips this.
  2. Cross-check the structural invariants the C++ side relies on
     (magic == "OT", version == 1, big-endian payload length, last 2
     bytes are CRC-16/CCITT-FALSE over the rest, etc.).

If you intentionally change the firmware default payload or the wire
format, regenerate the expected hex by running:

    python -c "from tests.test_firmware_parity import _firmware_hello_bytes; print(_firmware_hello_bytes().hex())"

and paste the new value into ``EXPECTED_HELLO_HEX`` below.
"""

from __future__ import annotations

import json

from opentama.ir.protocol import (
    CRC_SIZE,
    HEADER_SIZE,
    MAGIC,
    VERSION,
    Frame,
    FrameType,
    crc16,
    decode,
    encode,
)


# Mirrors firmware/m5stickc/platformio.ini build flags.
FIRMWARE_PET_NAME = "たころん"
FIRMWARE_PET_STAGE = "child"
FIRMWARE_PET_GP = 60


def _firmware_hello_payload() -> bytes:
    """Reproduce the JSON the firmware's snprintf in main.cpp emits.

    Format: ``{"name":"%s","stage":"%s","gp":%u}`` with no whitespace,
    UTF-8, the same key order as the firmware.
    """
    return (
        f'{{"name":"{FIRMWARE_PET_NAME}",'
        f'"stage":"{FIRMWARE_PET_STAGE}",'
        f'"gp":{FIRMWARE_PET_GP}}}'
    ).encode("utf-8")


def _firmware_hello_bytes() -> bytes:
    """Reproduce what the M5StickC firmware blinks out for its HELLO ping."""
    return encode(Frame(FrameType.HELLO, _firmware_hello_payload()))


# Pin the on-the-wire bytes. If this changes intentionally, regenerate
# (see module docstring).
EXPECTED_HELLO_HEX = (
    "4f540101002f"  # "OT" | ver=1 | type=HELLO | payload_len=47 (BE)
    "7b226e616d65223a22"            # {"name":"
    "e3819fe38193e3828de38293"      # たころん (UTF-8)
    "222c"                          # ",
    "227374616765223a22"            # "stage":"
    "6368696c64"                    # child
    "222c"                          # ",
    "226770223a3630"                # "gp":60
    "7d"                            # }
    "4e32"                          # CRC-16/CCITT-FALSE
)


def test_hello_bytes_locked():
    """The exact byte sequence the firmware should produce for HELLO."""
    actual = _firmware_hello_bytes()
    assert actual.hex() == EXPECTED_HELLO_HEX, (
        f"\nexpected: {EXPECTED_HELLO_HEX}"
        f"\nactual:   {actual.hex()}"
    )


def test_hello_structural_invariants():
    """Cross-check the layout the C++ encoder hard-codes."""
    payload = _firmware_hello_payload()
    encoded = _firmware_hello_bytes()

    # Header.
    assert encoded[:2] == MAGIC == b"OT"
    assert encoded[2] == VERSION == 1
    assert encoded[3] == int(FrameType.HELLO) == 1
    assert int.from_bytes(encoded[4:6], "big") == len(payload)

    # Payload.
    assert encoded[HEADER_SIZE : HEADER_SIZE + len(payload)] == payload

    # CRC: last 2 bytes, computed over magic..payload.
    body = encoded[: -CRC_SIZE]
    expected_crc = crc16(body)
    actual_crc = int.from_bytes(encoded[-CRC_SIZE:], "big")
    assert actual_crc == expected_crc


def test_python_round_trip_of_firmware_bytes():
    """The Python decoder must accept what the firmware emits."""
    encoded = _firmware_hello_bytes()
    decoded = decode(encoded)
    assert decoded.type == FrameType.HELLO
    assert decoded.json() == {
        "name": FIRMWARE_PET_NAME,
        "stage": FIRMWARE_PET_STAGE,
        "gp": FIRMWARE_PET_GP,
    }


def test_crc16_known_vector():
    """Sanity-check CRC-16/CCITT-FALSE against a public test vector.

    For input ``b"123456789"``, CRC-16/CCITT-FALSE = 0x29B1. Both the
    Python and C++ implementations must agree with this.
    """
    assert crc16(b"123456789") == 0x29B1
