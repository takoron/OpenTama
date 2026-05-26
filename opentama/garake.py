"""Feature-phone (ガラケー) interop — IrDA vCard / vNote → PeerSighting.

OpenTama's IR protocol is bespoke; real Japanese feature phones speak
the IrDA vObject family (vCard for the address book, vNote for memos,
vCal for calendar items). To accept a "赤外線で名刺を送りました" from a
colleague's ガラケー we don't need to teach the phone our protocol —
we just need to parse what it already sends.

This module provides:

* :func:`parse_vobject` — extract `(kind, fields)` from a single vObject
  block (BEGIN:VCARD / END:VCARD or BEGIN:VNOTE / END:VNOTE).
* :func:`parse_vobject_stream` — pull out *every* vObject from a byte
  blob, ignoring whatever wraps them. Tolerates UTF-8 and Shift-JIS.
* :func:`vobject_to_sighting` — convert one parsed vObject to a
  :class:`opentama.proximity.PeerSighting`. vCard's ``FN`` (formatted
  name) becomes ``peer_id``; ``NICKNAME`` becomes the sighting
  nickname.

What this module does **not** do:

* It does not speak OBEX. Many USB-IrDA adapters hand you raw vObject
  text after the OBEX layer has been stripped by the driver; this
  module assumes you're at that point. If your adapter delivers raw
  IrLAP frames you need an OBEX shim between them and this parser —
  that's deliberately out of scope for the PoC.
* It does not transmit. Sending a vCard *back* to a phone requires
  OBEX PUT, which is again out of scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable, Optional

if TYPE_CHECKING:
    from .proximity import PeerSighting


# --- decoding ---------------------------------------------------------------


# Encoding strategy:
#
#   1. Strict UTF-8 first — modern phones and any reasonable adapter
#      emit UTF-8.
#   2. Strict Shift-JIS second — old-school Japanese feature phones.
#   3. UTF-8 with replacement as a last resort — a vCard buried in
#      IrDA framing bytes (e.g. \x00 / \xff) lives here.
#
# We deliberately do **not** try cp932 (the Microsoft extension of
# Shift-JIS): cp932 accepts the lone byte \xff as the valid PUA
# code point U+F8F3, which means a UTF-8 vCard wrapped in a single
# \xff framing byte would "successfully" decode under cp932 — but the
# UTF-8 multi-byte sequences inside would get re-interpreted as
# mojibake. The strict-UTF-8 → strict-Shift-JIS → UTF-8-replace
# ladder gives us the correct text in every real case we care about.
_STRICT_ENCODINGS = ("utf-8", "shift_jis")


def _best_effort_decode(blob: bytes) -> str:
    for encoding in _STRICT_ENCODINGS:
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


# --- vObject parsing --------------------------------------------------------


@dataclass(frozen=True)
class VObject:
    """A parsed vCard / vNote block."""

    kind: str                        # "VCARD" / "VNOTE" / "VCALENDAR" / ...
    fields: dict[str, str]           # property name (UPPERCASE) -> value
    raw: str                         # original text, for debugging


_VOBJECT_RE = re.compile(
    r"BEGIN:(?P<kind>V[A-Z]+)\s*\r?\n(?P<body>.*?)\r?\nEND:(?P=kind)",
    re.DOTALL | re.IGNORECASE,
)
# vObject "logical lines" can be split across multiple physical lines by
# starting the continuation with whitespace. RFC 2425 §5.8.1.
_FOLDED_CONT = re.compile(r"\r?\n[ \t]")


def _unfold(body: str) -> list[str]:
    """Apply RFC 2425 line unfolding then split into logical lines."""
    unfolded = _FOLDED_CONT.sub("", body)
    return [ln for ln in unfolded.splitlines() if ln.strip()]


def parse_vobject(text: str) -> Optional[VObject]:
    """Parse a single vObject block.

    Returns ``None`` if no well-formed BEGIN/END pair is found. If
    there is more than one vObject in ``text``, only the first is
    returned — use :func:`parse_vobject_stream` to get them all.
    """
    m = _VOBJECT_RE.search(text)
    if m is None:
        return None
    kind = m.group("kind").upper()
    body = m.group("body")
    fields: dict[str, str] = {}
    for line in _unfold(body):
        if ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        # Strip parameters: "TEL;CELL" → "TEL", "BODY;CHARSET=UTF-8" → "BODY".
        key = key_part.split(";", 1)[0].strip().upper()
        if not key:
            continue
        # vObject quoted-printable / charset params are best-effort:
        # we just take the value verbatim, leaving the caller free to
        # interpret further if it cares.
        if key not in fields:  # first occurrence wins (matches phone behaviour)
            fields[key] = value.strip()
    return VObject(kind=kind, fields=fields, raw=m.group(0))


def parse_vobject_stream(blob: bytes) -> list[VObject]:
    """Find every vObject in ``blob``. Tolerant of wrapping/garbage."""
    text = _best_effort_decode(blob)
    out: list[VObject] = []
    for m in _VOBJECT_RE.finditer(text):
        parsed = parse_vobject(m.group(0))
        if parsed is not None:
            out.append(parsed)
    return out


# --- sighting conversion ---------------------------------------------------


def vobject_to_sighting(
    vobj: VObject,
    *,
    rssi_bucket: str = "close",
    clock: Callable[[], float] = lambda: 0.0,
) -> "Optional[PeerSighting]":
    """Convert one parsed vObject into a :class:`PeerSighting`.

    Mapping:

    - **vCard** → ``peer_id`` = ``FN`` (or ``N``-rebuilt, or
      ``NICKNAME`` as last resort); ``nickname`` = ``NICKNAME`` if
      different from ``peer_id``.
    - **vNote** → ``peer_id`` = the (unprefixed) ``BODY``; no nickname.
      This is the convention for the "memo を赤外線で送る" workflow
      where the body itself is the identifier (a pet name, a meeting
      tag, …).
    - Anything else returns ``None`` — we don't try to invent peer
      identifiers from random property bags.

    ``rssi_bucket`` defaults to ``"close"`` because IrDA needs the two
    devices aimed within ~1 m of each other, which always feels close
    relative to BLE / WiFi.
    """
    # Local import keeps proximity ↔ garake free of import cycles.
    from .proximity import PeerSighting

    now = clock()

    if vobj.kind == "VCARD":
        fn = vobj.fields.get("FN")
        n = vobj.fields.get("N")
        nickname = vobj.fields.get("NICKNAME")

        peer_id: Optional[str] = None
        # Preferred: FN (formatted name).
        if fn:
            peer_id = fn
        elif n:
            # vCard N is "Family;Given;Additional;Prefix;Suffix" — collapse
            # the first two non-empty parts.
            parts = [p.strip() for p in n.split(";")]
            parts = [p for p in parts if p][:2]
            if parts:
                peer_id = " ".join(parts)
        elif nickname:
            peer_id = nickname

        if peer_id is None:
            return None

        return PeerSighting(
            peer_id=peer_id,
            nickname=(nickname if nickname and nickname != peer_id else peer_id),
            lang=None,
            rssi_bucket=rssi_bucket,
            detected_at=now,
        )

    if vobj.kind == "VNOTE":
        body = vobj.fields.get("BODY")
        if not body:
            return None
        return PeerSighting(
            peer_id=body,
            nickname=body,
            lang=None,
            rssi_bucket=rssi_bucket,
            detected_at=now,
        )

    return None


def sightings_from_irda_blob(
    blob: bytes,
    *,
    rssi_bucket: str = "close",
    clock: Callable[[], float] = lambda: 0.0,
) -> list["PeerSighting"]:
    """High-level helper: bytes from an IrDA adapter → list of sightings.

    Each vObject in the blob becomes at most one sighting; vObjects
    that don't map (vCalendar, vObjects with no usable identifier)
    are silently dropped.
    """
    out: list["PeerSighting"] = []
    for vobj in parse_vobject_stream(blob):
        sighting = vobject_to_sighting(
            vobj, rssi_bucket=rssi_bucket, clock=clock
        )
        if sighting is not None:
            out.append(sighting)
    return out
