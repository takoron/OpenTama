"""Tests for SSID detection.

We mock ``subprocess.run`` so the tests are deterministic and
platform-independent.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from opentama import wifi


def _stub_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Return a callable suitable for monkeypatching ``subprocess.run``."""

    def runner(cmd, *args, **kwargs):  # noqa: ARG001 - mimic signature
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


# --- unknown platform -------------------------------------------------------


def test_unknown_platform_returns_none():
    assert wifi.get_current_ssid(platform="haiku-os") is None


# --- macOS ------------------------------------------------------------------


def test_macos_parses_networksetup_output(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        _stub_run(stdout="Current Wi-Fi Network: OfficeWiFi\n"),
    )
    assert wifi.get_current_ssid(platform="darwin") == "OfficeWiFi"


def test_macos_not_associated_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        _stub_run(stdout="You are not associated with an AirPort network.\n"),
    )
    assert wifi.get_current_ssid(platform="darwin") is None


def test_macos_command_missing_returns_none(monkeypatch: pytest.MonkeyPatch):
    def raise_missing(*a, **k):
        raise FileNotFoundError("networksetup not found")

    monkeypatch.setattr(subprocess, "run", raise_missing)
    assert wifi.get_current_ssid(platform="darwin") is None


def test_macos_timeout_returns_none(monkeypatch: pytest.MonkeyPatch):
    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="networksetup", timeout=5)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    assert wifi.get_current_ssid(platform="darwin") is None


# --- Linux ------------------------------------------------------------------


def test_linux_iwgetid_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        subprocess, "run", _stub_run(stdout="OfficeWiFi\n")
    )
    assert wifi.get_current_ssid(platform="linux") == "OfficeWiFi"


def test_linux_falls_back_to_nmcli(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []

    def runner(cmd, *args, **kwargs):  # noqa: ARG001
        calls.append(list(cmd))
        if cmd[0] == "iwgetid":
            raise FileNotFoundError
        # nmcli output
        return SimpleNamespace(
            returncode=0,
            stdout="no:OtherNet\nyes:OfficeWiFi\nno:Guest\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", runner)
    assert wifi.get_current_ssid(platform="linux") == "OfficeWiFi"
    # both tools were tried
    assert any("iwgetid" in c for c in calls)
    assert any("nmcli" in c for c in calls)


def test_linux_no_active_wifi(monkeypatch: pytest.MonkeyPatch):
    def runner(cmd, *args, **kwargs):  # noqa: ARG001
        if cmd[0] == "iwgetid":
            return SimpleNamespace(returncode=0, stdout="\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="no:Other\n", stderr="")

    monkeypatch.setattr(subprocess, "run", runner)
    assert wifi.get_current_ssid(platform="linux") is None


def test_linux_both_tools_missing(monkeypatch: pytest.MonkeyPatch):
    def raise_missing(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", raise_missing)
    assert wifi.get_current_ssid(platform="linux") is None


# --- Windows ----------------------------------------------------------------


WINDOWS_NETSH_OUTPUT = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6
    GUID                   : abc
    Physical address       : 00:11:22:33:44:55
    State                  : connected
    SSID                   : OfficeWiFi
    BSSID                  : 66:77:88:99:aa:bb
    Network type           : Infrastructure
"""


def test_windows_parses_netsh_output(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        subprocess, "run", _stub_run(stdout=WINDOWS_NETSH_OUTPUT)
    )
    assert wifi.get_current_ssid(platform="win32") == "OfficeWiFi"


def test_windows_bssid_is_not_confused_with_ssid(monkeypatch: pytest.MonkeyPatch):
    """A line beginning with 'BSSID' must not be picked up as the SSID."""
    output = "    BSSID                  : 66:77:88:99:aa:bb\n"
    monkeypatch.setattr(subprocess, "run", _stub_run(stdout=output))
    assert wifi.get_current_ssid(platform="win32") is None


def test_windows_command_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(subprocess, "run", _stub_run(returncode=1))
    assert wifi.get_current_ssid(platform="win32") is None
