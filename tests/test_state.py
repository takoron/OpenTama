"""Tests for state persistence."""

import json
import os
from pathlib import Path

import pytest

from opentama.state import (
    TamaState,
    delete_state,
    get_state_path,
    load_state,
    save_state,
)


def test_load_state_returns_none_when_missing(tmp_path: Path):
    path = tmp_path / "state.json"
    assert load_state(path) is None


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    state = TamaState(
        name="Pikatchi",
        company_ssid="OfficeWiFi",
        happiness=42.0,
        hunger=10.5,
        energy=66.0,
        growth_points=123.4,
        born_at=1000.0,
        last_tick_at=2000.0,
        total_office_seconds=3600.0,
        days_at_office=1,
        achievements=["hatched", "first_hour"],
    )
    save_state(state, path)
    loaded = load_state(path)
    assert loaded == state


def test_save_creates_parent_directory(tmp_path: Path):
    path = tmp_path / "deep" / "nested" / "state.json"
    state = TamaState(name="Deep")
    save_state(state, path)
    assert path.exists()


def test_save_is_atomic_no_partial_file(tmp_path: Path):
    # We can only test that no .tmp file lingers after a successful save.
    path = tmp_path / "state.json"
    save_state(TamaState(name="Atomic"), path)
    tmp = path.with_suffix(".json.tmp")
    assert not tmp.exists()


def test_unknown_keys_are_ignored(tmp_path: Path):
    """Forward compatibility: extra keys in the JSON should not crash load."""
    path = tmp_path / "state.json"
    data = {"name": "Future", "future_field": "ignored", "happiness": 50.0}
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_state(path)
    assert loaded is not None
    assert loaded.name == "Future"
    assert loaded.happiness == 50.0


def test_delete_state_removes_file(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(TamaState(name="Doomed"), path)
    assert delete_state(path) is True
    assert not path.exists()
    # second call returns False
    assert delete_state(path) is False


def test_get_state_path_honours_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "elsewhere" / "tama.json"
    monkeypatch.setenv("OPENTAMA_STATE_PATH", str(target))
    assert get_state_path() == target


def test_get_state_path_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENTAMA_STATE_PATH", raising=False)
    p = get_state_path()
    assert p.name == "state.json"
    assert p.parent.name == ".opentama"


def test_japanese_name_is_preserved(tmp_path: Path):
    """Non-ASCII names must roundtrip correctly."""
    path = tmp_path / "state.json"
    state = TamaState(name="たまごっち")
    save_state(state, path)
    loaded = load_state(path)
    assert loaded is not None
    assert loaded.name == "たまごっち"
