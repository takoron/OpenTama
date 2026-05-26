"""Proximity detection — log peer-pet sightings and produce daily digests.

OpenTama supports a two-tier UX for cross-pet encounters (issue #1):

1. **Background detection.** A pluggable :class:`Detector` quietly logs
   nearby OpenTama peers throughout the day. A concrete detector might
   sit on top of the existing USB-IR transport (a colleague's IR stick
   pings yours), Bluetooth LE advertisements, mDNS on the office WiFi,
   or a unit-test loopback. The detection layer only stores opaque peer
   IDs, optional public nicknames, a coarse signal-strength bucket,
   and a timestamp — never raw social metadata.

2. **Explicit exchange.** The owner reviews the day's sightings via
   ``opentama proximity digest`` and chooses which peers to actually
   transact with. The real exchange (greet / gift / visit / skill
   metadata) goes through the existing :mod:`opentama.ir.session`
   API. Nothing in this module ever auto-installs a skill or auto-
   gifts: humans gate every cross-pet action.

This module covers tier 1 plus the digest. Tier 2's *exchange* itself
is unchanged from v0.3.x.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Protocol


# --- data types -------------------------------------------------------------


@dataclass(frozen=True)
class PeerSighting:
    """A single observation of another OpenTama in physical proximity.

    Designed to be cheap to log (≈100 bytes JSONL per record) and to
    leak as little social information as possible. The payload is just
    an opaque peer id, an optional public nickname, an optional language
    tag, a coarse signal-strength bucket, and a timestamp.
    """

    peer_id: str
    nickname: Optional[str] = None
    lang: Optional[str] = None
    rssi_bucket: str = "unknown"  # "close" / "near" / "far" / "unknown"
    detected_at: float = 0.0  # unix timestamp


RSSI_BUCKETS = ("close", "near", "far", "unknown")
_BUCKET_PRIORITY = {b: i for i, b in enumerate(("unknown", "far", "near", "close"))}


# --- storage ----------------------------------------------------------------


def get_log_path() -> Path:
    """Resolve the JSONL log path, honouring ``OPENTAMA_PROXIMITY_LOG``."""
    env = os.environ.get("OPENTAMA_PROXIMITY_LOG")
    if env:
        return Path(env)
    return Path.home() / ".opentama" / "proximity.jsonl"


def append_sighting(
    sighting: PeerSighting, path: Optional[Path] = None
) -> None:
    """Append-only JSONL log: cheap to write, cheap to truncate by day."""
    p = path or get_log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(sighting), ensure_ascii=False) + "\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line)


def load_sightings(
    path: Optional[Path] = None,
    *,
    since: Optional[float] = None,
) -> list[PeerSighting]:
    """Read all sightings, optionally filtered to ``detected_at >= since``.

    Malformed lines (corrupt JSON, unknown keys, wrong types) are
    silently skipped — the log is append-only and we'd rather lose a
    record than refuse to start.
    """
    p = path or get_log_path()
    if not p.exists():
        return []
    out: list[PeerSighting] = []
    known = set(PeerSighting.__dataclass_fields__)
    with p.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            filtered = {k: v for k, v in data.items() if k in known}
            try:
                s = PeerSighting(**filtered)
            except TypeError:
                continue
            if since is not None and s.detected_at < since:
                continue
            out.append(s)
    return out


def clear_log(path: Optional[Path] = None) -> bool:
    """Delete the log file. Return True if anything was removed."""
    p = path or get_log_path()
    if p.exists():
        p.unlink()
        return True
    return False


# --- detection layer (abstract) ---------------------------------------------


class Detector(Protocol):
    """Anything that can yield :class:`PeerSighting` instances on demand.

    Concrete implementations live outside this file (USB-IR, BLE,
    mDNS, ...). They all share the same minimal surface so the CLI and
    digest path don't need to know which detector produced a sighting.
    """

    def poll(self, timeout: float = 0.0) -> list[PeerSighting]:
        ...


@dataclass
class LoopbackDetector:
    """In-memory detector for tests and the ``proximity record`` CLI.

    Push :class:`PeerSighting` instances onto the queue with
    :meth:`push`, then call :meth:`poll` to drain them. The CLI's
    ``record`` subcommand wraps this so the user can synthesise a
    sighting from the command line (useful for demos and for letting a
    plugin or external script feed in detections it produced itself).
    """

    queue: list[PeerSighting] = field(default_factory=list)

    def push(self, sighting: PeerSighting) -> None:
        self.queue.append(sighting)

    def poll(self, timeout: float = 0.0) -> list[PeerSighting]:
        out = list(self.queue)
        self.queue.clear()
        return out


# --- digest -----------------------------------------------------------------


@dataclass(frozen=True)
class PeerEntry:
    """Aggregated information about one peer over a window of time."""

    peer_id: str
    nickname: Optional[str]
    lang: Optional[str]
    sightings: int
    first_seen_at: float
    last_seen_at: float
    closest_bucket: str


@dataclass(frozen=True)
class Digest:
    """A summary of all peers seen during a window."""

    window_start: float
    window_end: float
    peers: list[PeerEntry]

    @property
    def peer_count(self) -> int:
        return len(self.peers)

    @property
    def total_sightings(self) -> int:
        return sum(e.sightings for e in self.peers)


def summarise(
    sightings: Iterable[PeerSighting],
    *,
    window_start: Optional[float] = None,
    window_end: Optional[float] = None,
) -> Digest:
    """Collapse raw sightings into one :class:`PeerEntry` per peer."""
    bucketed: dict[str, PeerEntry] = {}
    earliest = float("inf")
    latest = float("-inf")
    for s in sightings:
        if window_start is not None and s.detected_at < window_start:
            continue
        if window_end is not None and s.detected_at > window_end:
            continue
        earliest = min(earliest, s.detected_at)
        latest = max(latest, s.detected_at)
        existing = bucketed.get(s.peer_id)
        if existing is None:
            bucketed[s.peer_id] = PeerEntry(
                peer_id=s.peer_id,
                nickname=s.nickname,
                lang=s.lang,
                sightings=1,
                first_seen_at=s.detected_at,
                last_seen_at=s.detected_at,
                closest_bucket=s.rssi_bucket,
            )
        else:
            best = existing.closest_bucket
            if _BUCKET_PRIORITY.get(s.rssi_bucket, 0) > _BUCKET_PRIORITY.get(
                best, 0
            ):
                best = s.rssi_bucket
            bucketed[s.peer_id] = PeerEntry(
                peer_id=existing.peer_id,
                nickname=existing.nickname or s.nickname,
                lang=existing.lang or s.lang,
                sightings=existing.sightings + 1,
                first_seen_at=min(existing.first_seen_at, s.detected_at),
                last_seen_at=max(existing.last_seen_at, s.detected_at),
                closest_bucket=best,
            )

    peers = sorted(
        bucketed.values(),
        key=lambda e: (-e.sightings, e.first_seen_at),
    )

    if window_start is None:
        window_start = earliest if earliest != float("inf") else 0.0
    if window_end is None:
        window_end = latest if latest != float("-inf") else 0.0

    return Digest(
        window_start=window_start,
        window_end=window_end,
        peers=peers,
    )


def format_digest(digest: Digest) -> str:
    """Render a Digest as a human-readable plain-text summary."""
    if digest.peer_count == 0:
        return "今日のすれ違いはありませんでした。"
    lines = [f"今日 {digest.peer_count} 人とすれ違いました:"]
    for e in digest.peers:
        name = e.nickname or e.peer_id
        lang = f" [{e.lang}]" if e.lang else ""
        lines.append(
            f"  • {name}{lang}  — {e.sightings} 回, "
            f"closest: {e.closest_bucket}"
        )
    return "\n".join(lines)
