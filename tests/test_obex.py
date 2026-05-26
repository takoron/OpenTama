"""Tests for the OBEX PUT / vCard send module."""

from __future__ import annotations

import struct

import pytest

from opentama.ir.transport import LoopbackIRTransport
from opentama.obex import (
    DEFAULT_MAX_PACKET,
    HID_END_OF_BODY,
    HID_LENGTH,
    HID_NAME,
    HID_TYPE,
    OBEX_VERSION,
    OPCODE_CONNECT,
    OPCODE_DISCONNECT,
    OPCODE_PUT_FINAL,
    OBEXResponse,
    OBEXResponseError,
    OBEXTransportError,
    SendResult,
    build_body_header,
    build_connect_packet,
    build_disconnect_packet,
    build_length_header,
    build_name_header,
    build_put_packet,
    build_type_header,
    build_vcard_text,
    parse_response,
    send_vcard,
)


# --- low-level builders ----------------------------------------------------


def test_connect_packet_layout():
    pkt = build_connect_packet()
    opcode, length = struct.unpack(">BH", pkt[:3])
    assert opcode == OPCODE_CONNECT == 0x80
    assert length == len(pkt) == 7  # 3 header + 4 connect-info
    version, flags, max_packet = struct.unpack(">BBH", pkt[3:])
    assert version == OBEX_VERSION == 0x10
    assert flags == 0x00
    assert max_packet == DEFAULT_MAX_PACKET == 0x2000


def test_connect_packet_custom_max_packet():
    pkt = build_connect_packet(max_packet=4096)
    _, _, max_packet = struct.unpack(">BBH", pkt[3:])
    assert max_packet == 4096


def test_disconnect_packet_is_three_bytes():
    pkt = build_disconnect_packet()
    assert len(pkt) == 3
    opcode, length = struct.unpack(">BH", pkt)
    assert opcode == OPCODE_DISCONNECT == 0x81
    assert length == 3


# --- header builders -------------------------------------------------------


def test_name_header_encodes_utf16be_with_null():
    h = build_name_header("alice")
    hid, hlen = struct.unpack(">BH", h[:3])
    assert hid == HID_NAME == 0x01
    # 1 + 2 + 5*2 (UTF-16BE) + 2 (null terminator)
    assert hlen == 3 + 5 * 2 + 2
    assert h[3:] == "alice".encode("utf-16-be") + b"\x00\x00"


def test_name_header_handles_japanese():
    h = build_name_header("たころん")
    # Should be valid UTF-16BE — round-trip-decode the payload.
    payload = h[3:]
    # strip trailing nulls
    text = payload[:-2].decode("utf-16-be")
    assert text == "たころん"


def test_name_header_with_empty_string():
    h = build_name_header("")
    hid, hlen = struct.unpack(">BH", h[:3])
    assert hid == HID_NAME
    assert hlen == 3 + 2  # just the terminator
    assert h[3:] == b"\x00\x00"


def test_type_header_appends_null():
    h = build_type_header("text/x-vcard")
    hid, hlen = struct.unpack(">BH", h[:3])
    assert hid == HID_TYPE == 0x42
    assert h[3:] == b"text/x-vcard\x00"
    assert hlen == 3 + len("text/x-vcard") + 1


def test_length_header_is_uint32_be():
    h = build_length_header(1234567)
    hid, value = struct.unpack(">BI", h)
    assert hid == HID_LENGTH == 0xC3
    assert value == 1234567


def test_body_header_final_is_end_of_body():
    data = b"hello"
    h = build_body_header(data, final=True)
    hid, hlen = struct.unpack(">BH", h[:3])
    assert hid == HID_END_OF_BODY == 0x49
    assert hlen == 3 + len(data)
    assert h[3:] == data


def test_body_header_non_final_is_body():
    data = b"chunk"
    h = build_body_header(data, final=False)
    hid, _ = struct.unpack(">BH", h[:3])
    assert hid == 0x48


# --- put packet ------------------------------------------------------------


def test_put_packet_layout():
    body = b"BEGIN:VCARD\r\nFN:Test\r\nEND:VCARD\r\n"
    pkt = build_put_packet("test.vcf", "text/x-vcard", body)
    opcode, length = struct.unpack(">BH", pkt[:3])
    assert opcode == OPCODE_PUT_FINAL == 0x82
    assert length == len(pkt)
    # Headers in order: Name, Type, Length, End-of-Body.
    cursor = 3
    # Name
    hid, hlen = struct.unpack(">BH", pkt[cursor:cursor + 3])
    assert hid == HID_NAME
    cursor += hlen
    # Type
    hid, hlen = struct.unpack(">BH", pkt[cursor:cursor + 3])
    assert hid == HID_TYPE
    cursor += hlen
    # Length (uint32)
    hid, total_len = struct.unpack(">BI", pkt[cursor:cursor + 5])
    assert hid == HID_LENGTH
    assert total_len == len(body)
    cursor += 5
    # End-of-Body
    hid, hlen = struct.unpack(">BH", pkt[cursor:cursor + 3])
    assert hid == HID_END_OF_BODY
    body_bytes = pkt[cursor + 3:cursor + hlen]
    assert body_bytes == body
    cursor += hlen
    assert cursor == len(pkt)


def test_put_packet_non_final_opcode():
    pkt = build_put_packet("x.vcf", "text/x-vcard", b"x", final=False)
    opcode, _ = struct.unpack(">BH", pkt[:3])
    assert opcode == 0x02  # PUT non-final


# --- response parsing ------------------------------------------------------


def test_parse_response_success():
    raw = struct.pack(">BH", 0xA0, 3)
    resp = parse_response(raw)
    assert isinstance(resp, OBEXResponse)
    assert resp.opcode == 0xA0
    assert resp.length == 3
    assert resp.body == b""
    assert resp.ok is True
    assert resp.is_continue is False


def test_parse_response_continue():
    raw = struct.pack(">BH", 0x90, 3)
    resp = parse_response(raw)
    assert resp.ok is False
    assert resp.is_continue is True


def test_parse_response_with_body():
    body = b"hello"
    raw = struct.pack(">BH", 0xA0, 3 + len(body)) + body
    resp = parse_response(raw)
    assert resp.body == body
    assert resp.ok is True


def test_parse_response_error_class():
    raw = struct.pack(">BH", 0xC0, 3)  # Bad Request
    resp = parse_response(raw)
    assert resp.ok is False
    assert resp.opcode == 0xC0


def test_parse_response_truncated():
    with pytest.raises(Exception):
        parse_response(b"\x80")


# --- vCard builder ---------------------------------------------------------


def test_vcard_text_minimal():
    text = build_vcard_text(full_name="アリス")
    assert text.startswith("BEGIN:VCARD\r\n")
    assert text.endswith("END:VCARD\r\n")
    assert "VERSION:2.1\r\n" in text
    assert "FN:アリス\r\n" in text
    # Optional fields should be absent.
    assert "TEL" not in text
    assert "EMAIL" not in text
    assert "NICKNAME" not in text


def test_vcard_text_with_all_optional_fields():
    text = build_vcard_text(
        full_name="ボブ",
        nickname="ボブさん",
        note="meeting at 3pm",
        org="Accenture",
        tel="090-1234-5678",
        email="bob@example.com",
    )
    assert "FN:ボブ" in text
    assert "NICKNAME:ボブさん" in text
    assert "NOTE:meeting at 3pm" in text
    assert "ORG:Accenture" in text
    assert "TEL;CELL:090-1234-5678" in text
    assert "EMAIL;INTERNET:bob@example.com" in text


def test_vcard_text_uses_crlf_line_endings():
    text = build_vcard_text(full_name="x")
    # Pure CRLF — no bare \n
    assert text.replace("\r\n", "") == text.replace("\r\n", "").replace("\n", "")


def test_vcard_text_is_self_consistent_minimal_parse():
    """The vCard we emit can be re-extracted with a trivial parser.

    A full garake round-trip lives in the feat/garake-irda branch and
    is intentionally not depended on here so this PR stays independent.
    """
    text = build_vcard_text(
        full_name="アリス",
        nickname="アリスさん",
        tel="090-0000-0000",
    )
    # Trivial line-based scan: every property is "KEY[;params]:VALUE".
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        if ":" in raw and not raw.startswith("BEGIN") and not raw.startswith("END"):
            key_part, _, value = raw.partition(":")
            fields[key_part.split(";", 1)[0]] = value
    assert fields["FN"] == "アリス"
    assert fields["NICKNAME"] == "アリスさん"
    assert fields["TEL"] == "090-0000-0000"
    assert fields["VERSION"] == "2.1"


# --- send_vcard (high-level) ----------------------------------------------


class _MockPhone:
    """Pre-canned OBEX server that always responds with success.

    Hooks into a paired :class:`LoopbackIRTransport`: when the PC end
    sends a packet, this object reads it off the phone end and queues
    a hard-coded reply. We don't actually parse the inbound packet;
    real conformance tests would, but for this PoC we just want to
    exercise the PC-side state machine.
    """

    def __init__(self, phone_transport: LoopbackIRTransport) -> None:
        self.phone = phone_transport
        self.received: list[bytes] = []

    def respond_to(self, n_packets: int = 3) -> None:
        for _ in range(n_packets):
            raw = self.phone.recv(timeout=0.5)
            self.received.append(raw)
            # Mirror the opcode class — CONNECT/PUT/DISCONNECT all get
            # an 0xA0 (OK) back.
            self.phone.send(struct.pack(">BH", 0xA0, 3))


def test_send_vcard_round_trip(monkeypatch):
    pc, phone = LoopbackIRTransport.pair()

    import threading

    server = _MockPhone(phone)
    t = threading.Thread(target=server.respond_to, args=(3,))
    t.start()

    text = build_vcard_text(full_name="たころん")
    result = send_vcard(pc, text, name="takoron.vcf")

    t.join(timeout=5)
    assert isinstance(result, SendResult)
    assert result.ok is True
    assert result.connect_response is not None
    assert result.connect_response.opcode == 0xA0
    assert result.put_response is not None
    assert result.put_response.opcode == 0xA0
    # We sent 3 packets.
    assert len(server.received) == 3
    # First was CONNECT, second PUT, third DISCONNECT.
    assert server.received[0][0] == OPCODE_CONNECT
    assert server.received[1][0] == OPCODE_PUT_FINAL
    assert server.received[2][0] == OPCODE_DISCONNECT


def test_send_vcard_connect_failure():
    pc, phone = LoopbackIRTransport.pair()

    # Phone responds to CONNECT with an error.
    import threading

    def reply():
        phone.recv(timeout=0.5)
        phone.send(struct.pack(">BH", 0xC0, 3))  # Bad Request

    t = threading.Thread(target=reply)
    t.start()
    try:
        with pytest.raises(OBEXResponseError) as exc_info:
            send_vcard(pc, build_vcard_text(full_name="x"), name="x.vcf")
        assert exc_info.value.opcode == 0xC0
    finally:
        t.join(timeout=2)


def test_send_vcard_transport_timeout():
    pc, phone = LoopbackIRTransport.pair()
    # Phone never responds. send_vcard should raise OBEXTransportError
    # on the *connect* response — we don't even reach PUT.
    with pytest.raises(OBEXTransportError):
        send_vcard(
            pc,
            build_vcard_text(full_name="x"),
            name="x.vcf",
            timeout=0.2,
        )
