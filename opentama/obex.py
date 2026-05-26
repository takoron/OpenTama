"""OBEX PUT — send a vCard / vNote *to* a feature phone over IrDA.

This is the symmetric partner of :mod:`opentama.garake`: where that
module *receives* vObjects a phone has sent, this module *sends* a
vObject the user composed on the PC. Together they implement the
"M5StickC と同じ送受信" parity for the ガラケー lane.

The protocol on the wire is IrOBEX (IrDA Object Exchange) — the same
protocol Japanese feature phones use for 名刺の赤外線送信. We
implement just enough of it to put one small file onto a phone in a
single PUT body:

    CONNECT  →  ←  CONNECT response (success)
    PUT (final) with Name + Type + Length + End-of-Body
                →  ←  PUT response (success)
    DISCONNECT
                →  ←  DISCONNECT response

Each packet is a single contiguous byte string:

    +--------+------------+-----------------+
    | opcode | length(BE) | opcode-specific |
    | 1 byte | uint16     | payload         |
    +--------+------------+-----------------+

Headers inside the payload follow the same general shape — a 1-byte
header ID with a built-in length convention (high-bit nybble of the
ID tells you whether it's unicode/byte-sequence/4byte/1byte).

What we *do* implement here:

- CONNECT  (0x80) with the standard 4-byte connect info.
- PUT      (0x02 non-final / 0x82 final) with Name + Type + Length +
  End-of-Body headers.
- DISCONNECT (0x81).
- A small vCard 2.1 builder for the common case.
- A response parser that just pulls the opcode + length back out, so
  the caller can decide whether the server returned success (0xA0)
  or continue (0x90) or an error (0xCx / 0xDx).

What we *don't* implement:

- The OBEX layer **only**. Anything sitting under OBEX is the
  transport's problem. For USB-IrDA adapters that already expose a
  cooked OBEX-over-serial endpoint (or for testing over a paired
  loopback) this module is enough; raw IrLAP / IrLMP / TinyTP are
  out of scope.
- Multi-packet PUTs. Our payload fits comfortably in the default
  ~2 KB max-packet, which is what every phone we care about accepts.
- ABORT, GETs, SETPATH. Not needed for the "send one vCard" workflow.

No third-party Python dependencies; everything here is :mod:`struct`
and :mod:`urllib`-free.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .ir.transport import IRTransport


# --- opcodes ---------------------------------------------------------------


OPCODE_CONNECT = 0x80
OPCODE_DISCONNECT = 0x81
OPCODE_PUT = 0x02
OPCODE_PUT_FINAL = 0x82

# Response opcode high nybbles. 0xA-prefixed = success class, 0x9 =
# continue, 0xC = client error, 0xD = server error. We just use the
# specific common codes.
RESP_CONTINUE = 0x90
RESP_OK = 0xA0


# --- header IDs ------------------------------------------------------------


HID_NAME = 0x01            # null-terminated UTF-16BE Unicode string
HID_TYPE = 0x42            # null-terminated ASCII byte sequence
HID_LENGTH = 0xC3          # uint32 BE
HID_BODY = 0x48            # byte sequence (non-final body chunk)
HID_END_OF_BODY = 0x49     # byte sequence (final body chunk)
HID_CONNECTION_ID = 0xCB   # uint32 BE
HID_TARGET = 0x46          # byte sequence


# --- connection params -----------------------------------------------------


OBEX_VERSION = 0x10        # OBEX 1.0
OBEX_FLAGS = 0x00
DEFAULT_MAX_PACKET = 0x2000  # 8 KB


# --- exceptions ------------------------------------------------------------


class OBEXError(RuntimeError):
    """Base exception for OBEX-level failures."""


class OBEXResponseError(OBEXError):
    """The peer returned a non-success response opcode."""

    def __init__(self, opcode: int, packet: bytes) -> None:
        super().__init__(
            f"OBEX peer responded with opcode 0x{opcode:02x}; "
            f"raw packet: {packet.hex()}"
        )
        self.opcode = opcode
        self.packet = packet


class OBEXTransportError(OBEXError):
    """The transport closed or timed out before the exchange completed."""


# --- packet builders -------------------------------------------------------


def build_connect_packet(max_packet: int = DEFAULT_MAX_PACKET) -> bytes:
    """Build a CONNECT request packet (no Target = default OBEX session)."""
    # Connect-specific 4-byte info: version | flags | max-packet (BE 16).
    body = struct.pack(">BBH", OBEX_VERSION, OBEX_FLAGS, max_packet)
    # opcode | length-field | body
    total_len = 3 + len(body)
    return struct.pack(">BH", OPCODE_CONNECT, total_len) + body


def build_disconnect_packet() -> bytes:
    """Build an empty DISCONNECT packet."""
    return struct.pack(">BH", OPCODE_DISCONNECT, 3)


def build_name_header(name: str) -> bytes:
    """Encode a Name header: ID | uint16 length | UTF-16BE + 0x0000."""
    if name is None:
        name = ""
    encoded = name.encode("utf-16-be") + b"\x00\x00"
    h_len = 3 + len(encoded)  # 1-byte ID + 2-byte length + data
    return struct.pack(">BH", HID_NAME, h_len) + encoded


def build_type_header(mime_type: str) -> bytes:
    """Encode a Type header: ID | uint16 length | ASCII + 0x00."""
    encoded = mime_type.encode("ascii") + b"\x00"
    h_len = 3 + len(encoded)
    return struct.pack(">BH", HID_TYPE, h_len) + encoded


def build_length_header(total_length: int) -> bytes:
    """Encode a Length header: ID | uint32 BE."""
    return struct.pack(">BI", HID_LENGTH, total_length)


def build_body_header(data: bytes, *, final: bool = True) -> bytes:
    """Encode a Body / End-of-Body header. ``final=True`` uses End-of-Body."""
    hid = HID_END_OF_BODY if final else HID_BODY
    h_len = 3 + len(data)
    return struct.pack(">BH", hid, h_len) + data


def build_put_packet(
    name: str,
    mime_type: str,
    body: bytes,
    *,
    final: bool = True,
) -> bytes:
    """Build a complete PUT packet for a small (single-packet) file."""
    headers = (
        build_name_header(name)
        + build_type_header(mime_type)
        + build_length_header(len(body))
        + build_body_header(body, final=True)
    )
    opcode = OPCODE_PUT_FINAL if final else OPCODE_PUT
    total_len = 3 + len(headers)
    return struct.pack(">BH", opcode, total_len) + headers


# --- response parsing ------------------------------------------------------


@dataclass(frozen=True)
class OBEXResponse:
    opcode: int
    length: int
    body: bytes  # everything after the 3-byte header
    raw: bytes

    @property
    def ok(self) -> bool:
        """True if the opcode is in the success class (0xA0-0xAF)."""
        return (self.opcode & 0xF0) == 0xA0

    @property
    def is_continue(self) -> bool:
        return (self.opcode & 0x7F) == (RESP_CONTINUE & 0x7F)


def parse_response(packet: bytes) -> OBEXResponse:
    """Parse a single OBEX response packet (opcode | length | body)."""
    if len(packet) < 3:
        raise OBEXError(f"truncated OBEX response: {packet!r}")
    opcode, length = struct.unpack(">BH", packet[:3])
    if length != len(packet):
        # Some adapters truncate the wire reads; we tolerate length
        # under-read but reject obvious garbage.
        if length > len(packet):
            raise OBEXError(
                f"OBEX response claims {length} bytes but only "
                f"{len(packet)} delivered"
            )
    return OBEXResponse(
        opcode=opcode,
        length=length,
        body=packet[3:length],
        raw=packet,
    )


# --- vCard builder ---------------------------------------------------------


def build_vcard_text(
    *,
    full_name: str,
    nickname: Optional[str] = None,
    note: Optional[str] = None,
    org: Optional[str] = None,
    tel: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """Build a minimal vCard 2.1 text. Lines terminate with CRLF.

    The phone's address book will accept this as a single 名刺. Only
    ``full_name`` is required; everything else is optional and is
    silently skipped when absent.
    """
    lines = ["BEGIN:VCARD", "VERSION:2.1", f"FN:{full_name}"]
    # vCard 2.1 N is "Family;Given;Additional;Prefix;Suffix"; we put
    # the whole thing in the family slot since we don't ask the caller
    # to split it.
    lines.append(f"N:{full_name};;;;")
    if nickname:
        lines.append(f"NICKNAME:{nickname}")
    if org:
        lines.append(f"ORG:{org}")
    if tel:
        lines.append(f"TEL;CELL:{tel}")
    if email:
        lines.append(f"EMAIL;INTERNET:{email}")
    if note:
        lines.append(f"NOTE:{note}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


# --- session helper --------------------------------------------------------


@dataclass(frozen=True)
class SendResult:
    """Outcome of :func:`send_vcard`."""

    ok: bool
    connect_response: Optional[OBEXResponse]
    put_response: Optional[OBEXResponse]
    disconnect_response: Optional[OBEXResponse]


def _recv_response(
    transport: "IRTransport",
    timeout: float,
) -> OBEXResponse:
    """Read a single OBEX response from ``transport``.

    We make one ``recv`` call, then keep reading while more bytes are
    available *and* what we have doesn't yet satisfy the response's
    declared length field. This handles adapters that surface the
    response one chunk at a time.
    """
    raw = transport.recv(timeout=timeout)
    if not raw:
        raise OBEXTransportError(
            "no OBEX response received before timeout"
        )
    # If we already have a complete declared length, return early.
    if len(raw) >= 3:
        _opcode, length = struct.unpack(">BH", raw[:3])
        while len(raw) < length:
            more = transport.recv(timeout=timeout)
            if not more:
                break
            raw += more
    return parse_response(raw)


def send_vcard(
    transport: "IRTransport",
    vcard_text: str,
    *,
    name: str,
    mime_type: str = "text/x-vcard",
    timeout: float = 5.0,
) -> SendResult:
    """Send one vCard to a phone over an OBEX-capable transport.

    Performs CONNECT → PUT(final) → DISCONNECT, reading the response
    between each step. Raises :class:`OBEXResponseError` if any
    response carries a non-success opcode (anything outside 0xAx),
    and :class:`OBEXTransportError` if the transport drops bytes.

    ``name`` is the filename the phone will see ("alice.vcf" works as
    well as anything else). ``mime_type`` defaults to ``text/x-vcard``
    which is what most Japanese feature phones expect; ``text/vcard``
    is also fine on modern handsets.
    """
    body = vcard_text.encode("utf-8")

    # 1) CONNECT
    transport.send(build_connect_packet())
    connect_resp = _recv_response(transport, timeout)
    if not connect_resp.ok:
        raise OBEXResponseError(connect_resp.opcode, connect_resp.raw)

    # 2) PUT (single-packet)
    transport.send(build_put_packet(name, mime_type, body, final=True))
    put_resp = _recv_response(transport, timeout)
    if not put_resp.ok:
        raise OBEXResponseError(put_resp.opcode, put_resp.raw)

    # 3) DISCONNECT
    transport.send(build_disconnect_packet())
    try:
        disconnect_resp = _recv_response(transport, timeout)
    except OBEXTransportError:
        # Phones routinely close the channel before we read DISCONNECT
        # back. Treat that as success.
        disconnect_resp = None

    return SendResult(
        ok=True,
        connect_response=connect_resp,
        put_response=put_resp,
        disconnect_response=disconnect_resp,
    )
