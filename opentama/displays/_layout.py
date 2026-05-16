"""Visual-width helpers for the retro display backends.

Terminal columns are not 1:1 with Python ``len(str)`` once Japanese
characters or emoji enter the picture. This module provides a small
``vwidth`` (visual width) function and a ``vpad`` padder that uses it,
so feature-phone frames stay aligned regardless of payload.
"""

from __future__ import annotations

import unicodedata


def vwidth(s: str) -> int:
    """Approximate terminal column width of ``s``.

    East-Asian Wide and Fullwidth characters count as 2 columns; every
    BMP-and-above code point that falls into the common emoji blocks
    counts as 2 as well. Zero-width / combining / control characters
    count as 0.
    """
    w = 0
    for ch in s:
        if unicodedata.category(ch) in {"Mn", "Me", "Cf"}:
            continue
        if ord(ch) < 0x20:
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
            continue
        # Common emoji ranges (heuristic; covers 🍙🎮💤📡⚙🔋📶 etc.).
        cp = ord(ch)
        if (
            0x1F300 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x27BF
            or 0x1F000 <= cp <= 0x1F2FF
        ):
            w += 2
            continue
        w += 1
    return w


def vpad(s: str, width: int, char: str = " ") -> str:
    """Right-pad ``s`` with ``char`` until visual width == ``width``.

    If ``s`` is wider than ``width``, it is truncated (without splitting
    a wide glyph in two — those are dropped whole).
    """
    cur = vwidth(s)
    if cur == width:
        return s
    if cur < width:
        return s + char * (width - cur)
    # Truncate.
    out = []
    used = 0
    for ch in s:
        cw = vwidth(ch)
        if used + cw > width:
            break
        out.append(ch)
        used += cw
    return "".join(out) + char * (width - used)
