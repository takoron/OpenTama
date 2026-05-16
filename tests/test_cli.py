"""End-to-end tests for the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from opentama import cli
from opentama.state import load_state


@pytest.fixture
def state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "state.json"
    monkeypatch.setenv("OPENTAMA_STATE_PATH", str(p))
    return p


def test_init_creates_state_file(state_path: Path, capsys: pytest.CaptureFixture):
    rc = cli.main(["init", "Pikachu", "OfficeWiFi"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Pikachu" in captured.out
    assert state_path.exists()

    state = load_state(state_path)
    assert state is not None
    assert state.name == "Pikachu"
    assert state.company_ssid == "OfficeWiFi"


def test_init_without_force_refuses_overwrite(
    state_path: Path, capsys: pytest.CaptureFixture
):
    cli.main(["init", "First", "Net"])
    rc = cli.main(["init", "Second", "Net"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "already exists" in err


def test_init_with_force_overwrites(state_path: Path):
    cli.main(["init", "First", "Net"])
    cli.main(["init", "--force", "Second", "OtherNet"])
    state = load_state(state_path)
    assert state is not None
    assert state.name == "Second"
    assert state.company_ssid == "OtherNet"


def test_status_without_init_errors(
    state_path: Path, capsys: pytest.CaptureFixture
):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["status"])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "No OpenTama" in err


def test_status_after_init(state_path: Path, capsys: pytest.CaptureFixture):
    cli.main(["init", "Pikachu", "OfficeWiFi"])
    rc = cli.main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    # The pet's name and a stat bar should appear.
    assert "Pikachu" in out
    assert "Happiness" in out


def test_feed_increases_hunger(state_path: Path):
    cli.main(["init", "Eater", "Net"])
    state_before = load_state(state_path)
    assert state_before is not None
    # Reduce hunger directly so we can observe the bump.
    state_before.hunger = 50.0
    from opentama.state import save_state

    save_state(state_before, state_path)

    cli.main(["feed"])
    state_after = load_state(state_path)
    assert state_after is not None
    assert state_after.hunger > 50.0


def test_play_then_sleep(state_path: Path):
    cli.main(["init", "Player", "Net"])
    cli.main(["play"])
    s_after_play = load_state(state_path)
    assert s_after_play is not None
    cli.main(["sleep"])
    s_after_sleep = load_state(state_path)
    assert s_after_sleep is not None
    assert s_after_sleep.energy >= s_after_play.energy


def test_reset_removes_state(state_path: Path):
    cli.main(["init", "Goodbye", "Net"])
    assert state_path.exists()
    cli.main(["reset"])
    assert not state_path.exists()


def test_reset_when_no_state(state_path: Path, capsys: pytest.CaptureFixture):
    rc = cli.main(["reset"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No OpenTama" in out


def test_unknown_command_errors(state_path: Path):
    with pytest.raises(SystemExit):
        cli.main(["sing"])
