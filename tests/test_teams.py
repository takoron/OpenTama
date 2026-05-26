"""Tests for the Teams (Power Automate webhook) integration."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from opentama.core import Tamagotchi
from opentama.state import TamaState
from opentama.teams import (
    ADAPTIVE_CARD_SCHEMA_VERSION,
    ENV_VAR,
    USER_AGENT,
    NotifyResult,
    TeamsConfigError,
    TeamsTransportError,
    build_status_card,
    notify,
    post_card,
    resolve_webhook_url,
)


# --- fixtures ---------------------------------------------------------------


def _make_tama(**overrides: Any) -> Tamagotchi:
    """Build a Tamagotchi at a deterministic point in its life."""
    state_overrides = overrides.pop("state", {})
    defaults = dict(
        name="たころん",
        company_ssid="OfficeWiFi",
        happiness=70.0,
        hunger=50.0,
        energy=80.0,
        growth_points=60.0,  # ≥50 = child
        last_tick_at=1.0,
        days_at_office=2,
        achievements=["hatched", "first_hour", "day_at_office_2"],
    )
    defaults.update(state_overrides)
    state = TamaState(**defaults)
    return Tamagotchi(
        state,
        ssid_provider=overrides.get("ssid_provider", lambda: "OfficeWiFi"),
        clock=overrides.get("clock", lambda: 1.0),
    )


class _FakeResp:
    """Minimal stand-in for the object returned by urlopen()."""

    def __init__(self, code: int) -> None:
        self._code = code
        self.closed = False

    def getcode(self) -> int:
        return self._code

    def close(self) -> None:
        self.closed = True


# --- build_status_card ------------------------------------------------------


def test_card_envelope_shape():
    tama = _make_tama()
    payload = build_status_card(tama)
    assert payload["type"] == "message"
    assert len(payload["attachments"]) == 1
    att = payload["attachments"][0]
    assert att["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = att["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == ADAPTIVE_CARD_SCHEMA_VERSION
    assert isinstance(card["body"], list) and card["body"]


def test_card_title_has_name_and_stage():
    tama = _make_tama(state={"name": "たころん", "growth_points": 60.0})
    payload = build_status_card(tama)
    title_block = payload["attachments"][0]["content"]["body"][0]
    assert title_block["type"] == "TextBlock"
    assert "たころん" in title_block["text"]
    assert tama.stage.name in title_block["text"]


def test_card_summary_distinguishes_office_vs_away():
    at_office = build_status_card(_make_tama(ssid_provider=lambda: "OfficeWiFi"))
    away = build_status_card(_make_tama(ssid_provider=lambda: "HomeWiFi"))
    at_office_text = at_office["attachments"][0]["content"]["body"][1]["text"]
    away_text = away["attachments"][0]["content"]["body"][1]["text"]
    assert "出社中" in at_office_text
    assert "お留守番" in away_text


def test_card_factset_has_all_stats():
    tama = _make_tama(state={"happiness": 42.0, "hunger": 33.0, "energy": 22.0})
    payload = build_status_card(tama)
    factsets = [
        b for b in payload["attachments"][0]["content"]["body"]
        if b["type"] == "FactSet"
    ]
    assert len(factsets) == 1
    facts = {f["title"]: f["value"] for f in factsets[0]["facts"]}
    assert facts["Happiness"] == "42/100"
    assert facts["Hunger"] == "33/100"
    assert facts["Energy"] == "22/100"
    assert "Office days" in facts


def test_card_marks_sick_when_stat_low():
    # Sick threshold is 15; drop happiness below that.
    tama = _make_tama(state={"happiness": 10.0})
    assert tama.is_sick()
    summary = build_status_card(tama)["attachments"][0]["content"]["body"][1]["text"]
    assert "sick" in summary


def test_card_does_not_mark_sick_when_healthy():
    tama = _make_tama()
    assert not tama.is_sick()
    summary = build_status_card(tama)["attachments"][0]["content"]["body"][1]["text"]
    assert "sick" not in summary


def test_card_shows_recent_achievements():
    tama = _make_tama(state={"achievements": ["a", "b", "c", "d", "e"]})
    body = build_status_card(tama)["attachments"][0]["content"]["body"]
    achievement_blocks = [b for b in body if "🏅" in b.get("text", "")]
    assert len(achievement_blocks) == 1
    # Only the last three.
    text = achievement_blocks[0]["text"]
    assert "c" in text and "d" in text and "e" in text
    assert "a" not in text and "b" not in text


def test_card_omits_achievement_block_when_none():
    tama = _make_tama(state={"achievements": []})
    body = build_status_card(tama)["attachments"][0]["content"]["body"]
    assert not any("🏅" in b.get("text", "") for b in body)


def test_card_serialises_as_utf8_json():
    tama = _make_tama(state={"name": "🐙たころん"})
    payload = build_status_card(tama)
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    decoded = json.loads(blob.decode("utf-8"))
    assert "🐙たころん" in decoded["attachments"][0]["content"]["body"][0]["text"]


# --- resolve_webhook_url ----------------------------------------------------


def test_resolve_uses_env(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/hook")
    assert resolve_webhook_url() == "https://example.com/hook"


def test_resolve_explicit_beats_env(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/from-env")
    assert (
        resolve_webhook_url("https://example.com/explicit")
        == "https://example.com/explicit"
    )


def test_resolve_missing_raises(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(TeamsConfigError):
        resolve_webhook_url()


def test_resolve_rejects_non_http(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(TeamsConfigError):
        resolve_webhook_url("file:///etc/passwd")
    with pytest.raises(TeamsConfigError):
        resolve_webhook_url("ftp://example.com/")


# --- post_card --------------------------------------------------------------


def test_post_card_returns_status_and_posts_json():
    captured: dict[str, Any] = {}

    def opener(req: urllib.request.Request, timeout: float) -> Any:
        captured["url"] = req.full_url
        captured["body"] = req.data
        captured["method"] = req.get_method()
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["timeout"] = timeout
        return _FakeResp(202)

    payload = {"type": "message", "attachments": []}
    status = post_card(payload, "https://example.com/hook", opener=opener)
    assert status == 202
    assert captured["url"] == "https://example.com/hook"
    assert captured["method"] == "POST"
    assert json.loads(captured["body"].decode("utf-8")) == payload
    assert captured["headers"].get("content-type", "").startswith(
        "application/json"
    )
    assert captured["headers"].get("user-agent") == USER_AGENT
    assert captured["timeout"] == 10.0


def test_post_card_custom_timeout():
    captured: dict[str, Any] = {}

    def opener(req, timeout):
        captured["timeout"] = timeout
        return _FakeResp(200)

    post_card({}, "https://example.com/hook", timeout=2.5, opener=opener)
    assert captured["timeout"] == 2.5


def test_post_card_http_error_wraps():
    def opener(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", {}, None
        )

    with pytest.raises(TeamsTransportError) as exc_info:
        post_card({}, "https://example.com/hook", opener=opener)
    assert "400" in str(exc_info.value)


def test_post_card_url_error_wraps():
    def opener(req, timeout):
        raise urllib.error.URLError("connection refused")

    with pytest.raises(TeamsTransportError) as exc_info:
        post_card({}, "https://example.com/hook", opener=opener)
    assert "connection refused" in str(exc_info.value)


def test_post_card_closes_response():
    resp = _FakeResp(204)

    def opener(req, timeout):
        return resp

    post_card({}, "https://example.com/hook", opener=opener)
    assert resp.closed


# --- notify (high-level) ----------------------------------------------------


def test_notify_success(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/wh")
    captured: dict[str, Any] = {}

    def opener(req, timeout):
        captured["body"] = req.data
        return _FakeResp(200)

    tama = _make_tama()
    result = notify(tama, opener=opener)
    assert isinstance(result, NotifyResult)
    assert result.ok is True
    assert result.status == 200
    assert result.webhook_url == "https://example.com/wh"
    payload = json.loads(captured["body"].decode("utf-8"))
    assert payload["type"] == "message"
    assert payload["attachments"][0]["content"]["type"] == "AdaptiveCard"


def test_notify_non_2xx_reports_not_ok(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/wh")

    def opener(req, timeout):
        return _FakeResp(302)  # weird but not an HTTPError

    result = notify(_make_tama(), opener=opener)
    assert result.ok is False
    assert result.status == 302


def test_notify_propagates_config_error(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(TeamsConfigError):
        notify(_make_tama())


def test_notify_propagates_transport_error(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/wh")

    def opener(req, timeout):
        raise urllib.error.URLError("dns failure")

    with pytest.raises(TeamsTransportError):
        notify(_make_tama(), opener=opener)


# --- build_digest_card / notify_digest ------------------------------------


from opentama.proximity import PeerSighting, summarise
from opentama.teams import build_digest_card, notify_digest


def _digest_with_peers():
    return summarise(
        [
            PeerSighting(
                peer_id="p1",
                nickname="アリス",
                lang="ja",
                rssi_bucket="close",
                detected_at=100.0,
            ),
            PeerSighting(
                peer_id="p1",
                rssi_bucket="near",
                detected_at=110.0,
            ),
            PeerSighting(
                peer_id="p2",
                lang="en",
                rssi_bucket="far",
                detected_at=120.0,
            ),
        ]
    )


def test_digest_card_envelope_shape():
    payload = build_digest_card(_digest_with_peers())
    assert payload["type"] == "message"
    att = payload["attachments"][0]
    assert att["contentType"] == "application/vnd.microsoft.card.adaptive"
    card = att["content"]
    assert card["type"] == "AdaptiveCard"
    assert isinstance(card["body"], list) and card["body"]


def test_digest_card_includes_owner_name_in_title():
    payload = build_digest_card(_digest_with_peers(), owner_name="たころん")
    title = payload["attachments"][0]["content"]["body"][0]["text"]
    assert "たころん" in title


def test_digest_card_summary_has_counts():
    payload = build_digest_card(_digest_with_peers())
    summary = payload["attachments"][0]["content"]["body"][1]["text"]
    assert "2 人" in summary
    assert "3 回" in summary  # total sightings


def test_digest_card_factset_per_peer():
    payload = build_digest_card(_digest_with_peers())
    body = payload["attachments"][0]["content"]["body"]
    factsets = [b for b in body if b["type"] == "FactSet"]
    assert len(factsets) == 1
    titles = [f["title"] for f in factsets[0]["facts"]]
    # アリス first (2 sightings, closer), then p2 (1 sighting).
    assert titles[0].startswith("アリス")
    assert titles[1].startswith("p2")
    # Lang shown when present, suppressed when None.
    assert "[ja]" in titles[0]
    assert "[en]" in titles[1]
    values = [f["value"] for f in factsets[0]["facts"]]
    assert "2 回" in values[0]
    assert "closest=close" in values[0]
    assert "1 回" in values[1]
    assert "closest=far" in values[1]


def test_digest_card_empty():
    empty = summarise([])
    payload = build_digest_card(empty)
    body = payload["attachments"][0]["content"]["body"]
    summary = body[1]["text"]
    assert "ありません" in summary
    # No factset when empty.
    assert not any(b["type"] == "FactSet" for b in body)


def test_notify_digest_posts(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "https://example.com/wh")
    captured: dict[str, Any] = {}

    def opener(req, timeout):
        captured["body"] = req.data
        return _FakeResp(200)

    digest = _digest_with_peers()
    result = notify_digest(digest, owner_name="たころん", opener=opener)
    assert result.ok is True
    payload = json.loads(captured["body"].decode("utf-8"))
    assert payload["type"] == "message"
    title = payload["attachments"][0]["content"]["body"][0]["text"]
    assert "たころん" in title


def test_notify_digest_propagates_config_error(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(TeamsConfigError):
        notify_digest(_digest_with_peers())
