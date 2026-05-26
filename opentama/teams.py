"""Microsoft Teams integration for OpenTama.

OpenTama can post a snapshot of the pet to a Microsoft Teams channel via
a user-provided Power Automate workflow webhook (typically the "When a
Teams webhook request is received" trigger followed by "Post adaptive
card in a chat or channel"). The flow's HTTP URL is the only secret.
We never talk to Microsoft Graph and we never ask for OAuth scopes.

Setup (one-time, per user):

1. In Teams, decide which channel should receive pet notifications.
2. In Power Automate, create a flow with the trigger
   *When a Teams webhook request is received* and the action
   *Post adaptive card in a chat or channel*. Bind the card body to
   the trigger payload.
3. Copy the resulting HTTP URL.
4. Export it as ``OPENTAMA_TEAMS_WEBHOOK`` (or pass ``--webhook-url``
   on the CLI).

The payload is an Adaptive Card 1.4 wrapped in the
``{"type": "message", "attachments": [...]}`` envelope that the
Power Automate "post adaptive card" action expects. No third-party
dependencies — only :mod:`urllib`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from .core import Tamagotchi

if TYPE_CHECKING:
    from .proximity import Digest


# --- exceptions -------------------------------------------------------------


class TeamsConfigError(RuntimeError):
    """Raised when the webhook URL cannot be resolved or is malformed."""


class TeamsTransportError(RuntimeError):
    """Raised when posting to the webhook fails at the network / HTTP level."""


# --- payload construction ---------------------------------------------------


ENV_VAR = "OPENTAMA_TEAMS_WEBHOOK"
ADAPTIVE_CARD_SCHEMA_VERSION = "1.4"
USER_AGENT = "OpenTama-Teams/0.4"


def _fact(name: str, value: str) -> dict[str, str]:
    return {"title": name, "value": value}


def build_status_card(tama: Tamagotchi) -> dict[str, Any]:
    """Build the JSON payload for an Adaptive Card describing ``tama``.

    The result is a fully-formed ``{"type": "message", ...}`` envelope
    suitable for the Power Automate "Post adaptive card in a chat or
    channel" action — just dump it as JSON and POST as-is.
    """
    s = tama.state
    stage = tama.stage.name
    at_office = tama.is_at_office()
    sick = tama.is_sick()

    title = f"🐙 {s.name} — {stage}"
    summary_parts = [
        "出社中" if at_office else "お留守番",
        f"経験 {int(s.growth_points)} gp",
    ]
    if sick:
        summary_parts.append("⚠️ sick")
    summary = "  /  ".join(summary_parts)

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": summary,
            "wrap": True,
            "spacing": "Small",
            "isSubtle": True,
        },
        {
            "type": "FactSet",
            "facts": [
                _fact("Happiness", f"{int(s.happiness)}/100"),
                _fact("Hunger", f"{int(s.hunger)}/100"),
                _fact("Energy", f"{int(s.energy)}/100"),
                _fact("Office days", str(s.days_at_office)),
            ],
        },
    ]

    if s.achievements:
        # Most recent three, oldest-first so the latest reads last.
        body.append(
            {
                "type": "TextBlock",
                "text": "🏅 " + ", ".join(s.achievements[-3:]),
                "wrap": True,
                "spacing": "Small",
            }
        )

    card: dict[str, Any] = {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": ADAPTIVE_CARD_SCHEMA_VERSION,
        "body": body,
    }
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }


# --- URL resolution ---------------------------------------------------------


def resolve_webhook_url(explicit: Optional[str] = None) -> str:
    """Return a Teams webhook URL.

    Precedence: explicit argument > ``OPENTAMA_TEAMS_WEBHOOK`` env var.
    Raises :class:`TeamsConfigError` if no URL is available, or if the
    URL is not an HTTP(S) URL — we refuse ``file://``, ``ftp://`` etc.
    to avoid an obvious data-exfiltration footgun if the env var is
    ever tampered with.
    """
    url = explicit or os.environ.get(ENV_VAR)
    if not url:
        raise TeamsConfigError(
            f"No Teams webhook URL configured. "
            f"Set {ENV_VAR} or pass --webhook-url."
        )
    if not url.startswith(("https://", "http://")):
        raise TeamsConfigError(
            f"Refusing to use a non-HTTP(S) webhook URL: {url!r}"
        )
    return url


# --- transport --------------------------------------------------------------

# Pluggable opener so tests can intercept the network call without monkeypatching
# urllib at module scope.
Opener = Callable[[urllib.request.Request, float], Any]


def _default_opener(req: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(req, timeout=timeout)


def post_card(
    payload: dict[str, Any],
    webhook_url: str,
    *,
    timeout: float = 10.0,
    opener: Optional[Opener] = None,
) -> int:
    """POST ``payload`` to ``webhook_url`` as JSON, return HTTP status.

    Raises :class:`TeamsTransportError` for any HTTP or network failure.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": USER_AGENT,
        },
    )
    _open = opener or _default_opener
    try:
        resp = _open(req, timeout)
    except urllib.error.HTTPError as e:
        raise TeamsTransportError(f"HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise TeamsTransportError(f"network error: {e.reason}") from e
    try:
        return int(resp.getcode())
    finally:
        close = getattr(resp, "close", None)
        if callable(close):
            close()


# --- high-level helper ------------------------------------------------------


@dataclass(frozen=True)
class NotifyResult:
    """Result of a :func:`notify` call."""

    ok: bool
    status: int
    webhook_url: str


def notify(
    tama: Tamagotchi,
    *,
    webhook_url: Optional[str] = None,
    timeout: float = 10.0,
    opener: Optional[Opener] = None,
) -> NotifyResult:
    """Build a status card for ``tama`` and POST it to Teams.

    Raises :class:`TeamsConfigError` if no webhook URL is available,
    or :class:`TeamsTransportError` if the HTTP call fails.
    """
    url = resolve_webhook_url(webhook_url)
    payload = build_status_card(tama)
    status = post_card(payload, url, timeout=timeout, opener=opener)
    return NotifyResult(ok=200 <= status < 300, status=status, webhook_url=url)


# --- proximity digest card --------------------------------------------------


def build_digest_card(
    digest: "Digest", *, owner_name: Optional[str] = None
) -> dict[str, Any]:
    """Build a Teams Adaptive Card summarising a proximity digest.

    The card mirrors the plain-text format from
    :func:`opentama.proximity.format_digest`: a title naming the owner
    (if known), a one-line summary with the peer count, and a FactSet
    where each peer is one row ``"nickname [lang]"`` → ``"N 回 / closest=X"``.
    If the digest is empty the card simply says so.
    """
    title = (
        f"📡 {owner_name} のすれ違いログ"
        if owner_name
        else "📡 OpenTama すれ違いログ"
    )

    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        }
    ]

    if digest.peer_count == 0:
        body.append(
            {
                "type": "TextBlock",
                "text": "今日のすれ違いはありませんでした。",
                "wrap": True,
                "spacing": "Small",
                "isSubtle": True,
            }
        )
    else:
        body.append(
            {
                "type": "TextBlock",
                "text": (
                    f"今日 {digest.peer_count} 人とすれ違いました "
                    f"(計 {digest.total_sightings} 回)"
                ),
                "wrap": True,
                "spacing": "Small",
                "isSubtle": True,
            }
        )
        facts: list[dict[str, str]] = []
        for e in digest.peers:
            name = e.nickname or e.peer_id
            lang = f" [{e.lang}]" if e.lang else ""
            facts.append(
                _fact(
                    f"{name}{lang}",
                    f"{e.sightings} 回 / closest={e.closest_bucket}",
                )
            )
        body.append({"type": "FactSet", "facts": facts})

    card = {
        "type": "AdaptiveCard",
        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
        "version": ADAPTIVE_CARD_SCHEMA_VERSION,
        "body": body,
    }
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }
        ],
    }


def notify_digest(
    digest: "Digest",
    *,
    owner_name: Optional[str] = None,
    webhook_url: Optional[str] = None,
    timeout: float = 10.0,
    opener: Optional[Opener] = None,
) -> NotifyResult:
    """Post a proximity digest to Teams as an Adaptive Card.

    Same semantics as :func:`notify` but for the "today's sightings"
    summary rather than a pet status snapshot. Raises
    :class:`TeamsConfigError` / :class:`TeamsTransportError`.
    """
    url = resolve_webhook_url(webhook_url)
    payload = build_digest_card(digest, owner_name=owner_name)
    status = post_card(payload, url, timeout=timeout, opener=opener)
    return NotifyResult(ok=200 <= status < 300, status=status, webhook_url=url)
