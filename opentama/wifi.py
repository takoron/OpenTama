"""Cross-platform current Wi-Fi SSID detection.

Returns ``None`` whenever the SSID cannot be determined (e.g. wired
connection, Wi-Fi off, command unavailable, permission denied).
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

# Sentinels that platform tools sometimes emit instead of a real SSID.
_BAD_SSIDS = {"", "--", "you are not associated with an airport network."}


def _clean(ssid: str) -> Optional[str]:
    s = ssid.strip().strip('"')
    if not s or s.lower() in _BAD_SSIDS:
        return None
    return s


def get_current_ssid(platform: str | None = None) -> Optional[str]:
    """Return the SSID of the currently associated Wi-Fi network, or ``None``."""
    plat = platform if platform is not None else sys.platform
    if plat == "darwin":
        return _get_ssid_macos()
    if plat.startswith("linux"):
        return _get_ssid_linux()
    if plat in ("win32", "cygwin"):
        return _get_ssid_windows()
    return None


# --- macOS ------------------------------------------------------------------


def _get_ssid_macos() -> Optional[str]:
    # ``networksetup -getairportnetwork`` works on modern macOS without
    # requiring the deprecated ``airport`` binary.
    for iface in ("en0", "en1"):
        try:
            r = subprocess.run(
                ["networksetup", "-getairportnetwork", iface],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        if r.returncode != 0:
            continue
        line = r.stdout.strip()
        # "Current Wi-Fi Network: MyOfficeSSID"
        if ":" in line:
            ssid = _clean(line.split(":", 1)[1])
            if ssid is not None:
                return ssid
    return None


# --- Linux ------------------------------------------------------------------


def _get_ssid_linux() -> Optional[str]:
    # Prefer iwgetid (universal, returns just the SSID).
    try:
        r = subprocess.run(
            ["iwgetid", "-r"], capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            ssid = _clean(r.stdout)
            if ssid is not None:
                return ssid
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # Fallback: NetworkManager's nmcli.
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        # Lines look like "yes:OfficeWiFi" or "no:OtherNet".
        if line.startswith("yes:"):
            return _clean(line.split(":", 1)[1])
    return None


# --- Windows ----------------------------------------------------------------


def _get_ssid_windows() -> Optional[str]:
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    for raw in r.stdout.splitlines():
        line = raw.strip()
        # Avoid matching "BSSID".
        if line.startswith("SSID") and not line.startswith("BSSID"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                return _clean(parts[1])
    return None
