"""Command-line interface for OpenTama.

Usage:
  python -m opentama init <name> <company-ssid>
  python -m opentama status
  python -m opentama feed
  python -m opentama play
  python -m opentama sleep
  python -m opentama reset
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Sequence

from .core import Tamagotchi, TickResult
from .state import (
    TamaState,
    delete_state,
    get_state_path,
    load_state,
    save_state,
)
from .wifi import get_current_ssid


# --- rendering --------------------------------------------------------------


def _bar(value: float, width: int = 10) -> str:
    filled = max(0, min(width, int(value / (100 / width))))
    return "█" * filled + "·" * (width - filled)


def render_status(tama: Tamagotchi, tick: TickResult) -> str:
    s = tama.state
    stage = tama.stage
    at_office = "✅ at office" if tick.at_office else "🏠 away"
    ssid = tick.ssid or "(no wifi)"
    lines = [
        stage.art,
        "",
        f"Name:      {s.name}  ({stage.name}, {int(s.growth_points)} gp)",
        f"Happiness: {_bar(s.happiness)} {int(s.happiness):3d}/100",
        f"Hunger:    {_bar(s.hunger)} {int(s.hunger):3d}/100",
        f"Energy:    {_bar(s.energy)} {int(s.energy):3d}/100",
        f"Office:    {s.total_office_seconds / 3600:.1f} h total"
        f"   ({s.days_at_office} day(s))",
        f"WiFi:      {ssid}  →  {at_office}",
    ]
    if tick.events:
        lines.append("")
        lines.append("Events: " + ", ".join(tick.events))
    return "\n".join(lines)


# --- helpers ----------------------------------------------------------------


def _require_state() -> TamaState:
    state = load_state()
    if state is None:
        print(
            "No OpenTama found at "
            f"{get_state_path()}.\n"
            "Run `python -m opentama init <name> <company-ssid>` to hatch one.",
            file=sys.stderr,
        )
        sys.exit(1)
    return state


def _build(state: TamaState) -> Tamagotchi:
    return Tamagotchi(state, ssid_provider=get_current_ssid)


# --- subcommands ------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    if load_state() is not None and not args.force:
        print(
            "An OpenTama already exists. Use --force to overwrite, or "
            "`python -m opentama reset` to remove it first.",
            file=sys.stderr,
        )
        return 1
    now = time.time()
    state = TamaState(
        name=args.name,
        company_ssid=args.ssid,
        born_at=now,
        last_tick_at=0.0,  # first tick anchors the clock
    )
    save_state(state)
    print(f"🥚 {args.name} hatched! Office SSID: {args.ssid}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = _require_state()
    tama = _build(state)
    tick = tama.tick()
    save_state(tama.state)
    if getattr(args, "display", None):
        from . import displays
        try:
            print(displays.render_with_tama(args.display, tama))
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 1
        # Always include the WiFi/office summary under the phone frame.
        ssid = tick.ssid or "(no wifi)"
        loc = "✅ at office" if tick.at_office else "🏠 away"
        print(f"\nWiFi: {ssid}  →  {loc}")
        if tick.events:
            print("Events: " + ", ".join(tick.events))
    else:
        print(render_status(tama, tick))
    return 0


def cmd_feed(args: argparse.Namespace) -> int:
    state = _require_state()
    tama = _build(state)
    tama.tick()
    tama.feed()
    save_state(tama.state)
    print(f"🍙 fed.   Hunger: {int(tama.state.hunger)}/100")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    state = _require_state()
    tama = _build(state)
    tama.tick()
    tama.play()
    save_state(tama.state)
    print(
        f"🎮 played. Happiness: {int(tama.state.happiness)}/100"
        f"   Energy: {int(tama.state.energy)}/100"
    )
    return 0


def cmd_sleep(args: argparse.Namespace) -> int:
    state = _require_state()
    tama = _build(state)
    tama.tick()
    tama.sleep()
    save_state(tama.state)
    print(f"💤 slept. Energy: {int(tama.state.energy)}/100")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    if delete_state():
        print("OpenTama removed.")
    else:
        print("No OpenTama to remove.")
    return 0


# --- Teams subcommands ------------------------------------------------------


def cmd_teams_notify(args: argparse.Namespace) -> int:
    from .teams import TeamsConfigError, TeamsTransportError, notify

    state = _require_state()
    tama = _build(state)
    tama.tick()  # advance growth/decay so the snapshot is current
    save_state(tama.state)

    try:
        result = notify(
            tama,
            webhook_url=getattr(args, "webhook_url", None),
            timeout=args.timeout,
        )
    except TeamsConfigError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    except TeamsTransportError as e:
        print(f"❌ Teams transport failed: {e}", file=sys.stderr)
        return 1

    if result.ok:
        print(f"📨 Teams notified ({result.status}).")
        return 0
    print(
        f"❌ Teams responded with HTTP {result.status}.",
        file=sys.stderr,
    )
    return 1


# --- Proximity subcommands --------------------------------------------------


def cmd_proximity_record(args: argparse.Namespace) -> int:
    from .proximity import PeerSighting, RSSI_BUCKETS, append_sighting

    if args.rssi not in RSSI_BUCKETS:
        print(
            f"❌ rssi must be one of {RSSI_BUCKETS}; got {args.rssi!r}",
            file=sys.stderr,
        )
        return 2
    now = time.time() if args.at is None else float(args.at)
    s = PeerSighting(
        peer_id=args.peer_id,
        nickname=args.nickname,
        lang=args.lang,
        rssi_bucket=args.rssi,
        detected_at=now,
    )
    append_sighting(s)
    print(
        f"📡 recorded sighting of {s.peer_id}"
        + (f" ({s.nickname})" if s.nickname else "")
    )
    return 0


def cmd_proximity_list(args: argparse.Namespace) -> int:
    from .proximity import load_sightings

    since = float(args.since) if args.since is not None else None
    rows = load_sightings(since=since)
    if not rows:
        print("(no sightings)")
        return 0
    for s in rows:
        name = s.nickname or s.peer_id
        lang = f" [{s.lang}]" if s.lang else ""
        print(
            f"{s.detected_at:>14.2f}  {s.rssi_bucket:>7}  "
            f"{name}{lang}"
        )
    return 0


def cmd_proximity_digest(args: argparse.Namespace) -> int:
    from .proximity import format_digest, load_sightings, summarise

    since = float(args.since) if args.since is not None else None
    sightings = load_sightings(since=since)
    digest = summarise(sightings)
    print(format_digest(digest))

    if args.notify_teams:
        from .teams import TeamsConfigError, TeamsTransportError, notify_digest

        # Owner name: explicit --owner > pet name from state > None.
        owner = args.owner
        if owner is None:
            state = load_state()
            if state is not None:
                owner = state.name
        try:
            result = notify_digest(
                digest,
                owner_name=owner,
                webhook_url=getattr(args, "webhook_url", None),
                timeout=args.timeout,
            )
        except TeamsConfigError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
        except TeamsTransportError as e:
            print(f"❌ Teams transport failed: {e}", file=sys.stderr)
            return 1
        if result.ok:
            print(f"📨 Teams notified ({result.status}).")
            return 0
        print(
            f"❌ Teams responded with HTTP {result.status}.",
            file=sys.stderr,
        )
        return 1

    return 0


def cmd_proximity_clear(args: argparse.Namespace) -> int:
    from .proximity import clear_log

    if clear_log():
        print("proximity log cleared.")
    else:
        print("no proximity log to clear.")
    return 0


def cmd_proximity_scan(args: argparse.Namespace) -> int:
    """Listen on an IR transport for ``--duration`` seconds, log peers seen."""
    from .proximity import (
        IRProximityDetector,
        RSSI_BUCKETS,
        append_sighting,
    )

    if args.rssi not in RSSI_BUCKETS:
        print(
            f"❌ rssi must be one of {RSSI_BUCKETS}; got {args.rssi!r}",
            file=sys.stderr,
        )
        return 2

    transport = _open_transport(args.port, getattr(args, "baud", None))
    detector = IRProximityDetector(transport, rssi_bucket=args.rssi)

    end = time.time() + args.duration
    seen = 0
    print(
        f"📡 scanning IR on {args.port} for {args.duration:.0f}s "
        f"(rssi={args.rssi})..."
    )
    try:
        while time.time() < end:
            remaining = max(0.0, end - time.time())
            sightings = detector.poll(timeout=min(0.5, remaining))
            for s in sightings:
                append_sighting(s)
                seen += 1
                name = s.nickname or s.peer_id
                print(f"  📡 {name}  [{s.rssi_bucket}]")
    finally:
        transport.close()

    print(f"scan complete — {seen} sighting(s) logged.")
    return 0


# --- IR subcommands ---------------------------------------------------------


def _open_transport(uri: str, baud: int | None):
    from .ir.transport import SerialIRTransport, open_transport

    if baud is not None and uri.startswith("serial://"):
        # Apply baud override.
        port = uri[len("serial://"):]
        if "?" in port:
            port = port.split("?", 1)[0]
        return SerialIRTransport(port, baud)
    return open_transport(uri)


def _make_ir_cmd(verb: str):
    def handler(args: argparse.Namespace) -> int:
        from .ir.session import Session

        state = _require_state()
        tama = _build(state)
        tama.tick()  # keep stats current

        transport = _open_transport(args.port, getattr(args, "baud", None))
        try:
            session = Session(tama, transport, timeout=args.timeout)
            if verb == "greet":
                result = session.greet()
            elif verb == "gift":
                result = session.gift(kind=args.kind)
            elif verb == "visit":
                result = session.visit()
            elif verb == "listen":
                result = session.serve_once()
            else:  # pragma: no cover - argparse blocks this
                raise RuntimeError(verb)
        finally:
            transport.close()

        save_state(tama.state)

        if not result.ok:
            print(f"❌ {verb} failed: {result.error}", file=sys.stderr)
            return 1
        if result.peer is not None:
            print(
                f"📡 {verb} ↔ {result.peer.name} "
                f"({result.peer.stage}, {result.peer.growth_points}gp)"
            )
        else:
            print(f"📡 {verb} ok")
        return 0

    return handler


# --- plugin subcommands -----------------------------------------------------


def cmd_plugin_list(args: argparse.Namespace) -> int:
    from .plugins import PluginLoader, TrustStore

    loader = PluginLoader()
    manifests = loader.discover()
    if not manifests:
        print(f"(no plugins in {loader.plugin_dir})")
        return 0
    trust = TrustStore.load()
    for m in manifests:
        trusted = "✓ trusted" if trust.is_trusted(m) else "  untrusted"
        caps = ", ".join(c.value for c in m.capabilities) or "(none)"
        print(f"{trusted}  {m.name} {m.version}  [{caps}]  sha256={m.sha256[:12]}…")
    return 0


def cmd_plugin_trust(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .plugins import TrustStore, parse_manifest, verify_integrity

    manifest = parse_manifest(Path(args.path))
    verify_integrity(manifest)
    store = TrustStore.load()
    store.trust(manifest)
    print(f"✓ trusted {manifest.trust_key} (sha256={manifest.sha256})")
    return 0


def cmd_plugin_revoke(args: argparse.Namespace) -> int:
    from .plugins import TrustStore

    store = TrustStore.load()
    if store.revoke(args.trust_key):
        print(f"revoked {args.trust_key}")
        return 0
    print(f"{args.trust_key} was not trusted", file=sys.stderr)
    return 1


def cmd_plugin_checksum(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .plugins import file_sha256

    print(file_sha256(Path(args.path)))
    return 0


def cmd_plugin_run(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .plugins import PluginLoader, make_context

    loader = PluginLoader()
    # locate by name
    matches = [m for m in loader.discover() if m.name == args.name]
    if not matches:
        print(f"plugin not found: {args.name}", file=sys.stderr)
        return 1
    loaded = loader.load(matches[0])

    state = _require_state()
    tama = _build(state)
    tama.tick()
    transport = None
    if args.port:
        transport = _open_transport(args.port, None)
    try:
        ctx = make_context(
            capabilities=set(loaded.manifest.capabilities),
            tama=tama,
            transport=transport,
        )
        loaded.instance.on_load(ctx)
        result = loaded.instance.run(ctx)
    finally:
        if transport is not None:
            transport.close()
    save_state(tama.state)
    if result is not None:
        print(result)
    return 0


# --- display subcommands ----------------------------------------------------


def cmd_display_list(args: argparse.Namespace) -> int:
    from . import displays

    for name in displays.DISPLAYS:
        print(name)
    return 0


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opentama",
        description="OpenTama — a Tamagotchi that grows when you come to the office.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="Hatch a new OpenTama.")
    pi.add_argument("name", help="The pet's name.")
    pi.add_argument("ssid", help="Your company WiFi SSID.")
    pi.add_argument("--force", action="store_true", help="Overwrite existing pet.")
    pi.set_defaults(func=cmd_init)

    ps = sub.add_parser("status", help="Show the pet's current status.")
    ps.add_argument(
        "--display",
        default=None,
        help="Render inside a retro feature-phone frame: monokuro / iro / wide.",
    )
    ps.set_defaults(func=cmd_status)

    pf = sub.add_parser("feed", help="Feed the pet.")
    pf.set_defaults(func=cmd_feed)

    pp = sub.add_parser("play", help="Play with the pet.")
    pp.set_defaults(func=cmd_play)

    pz = sub.add_parser("sleep", help="Let the pet rest.")
    pz.set_defaults(func=cmd_sleep)

    pr = sub.add_parser("reset", help="Delete the saved pet.")
    pr.set_defaults(func=cmd_reset)

    # --- ir -------------------------------------------------------------
    pir = sub.add_parser("ir", help="USB-IR communication with another OpenTama.")
    pir_sub = pir.add_subparsers(dest="ir_cmd", required=True)

    for verb, helptext in [
        ("greet", "Greet a peer over IR."),
        ("gift", "Send a gift over IR."),
        ("visit", "Visit a peer (greet + mutual happiness boost)."),
        ("listen", "Act as the responder for one inbound message."),
    ]:
        sp = pir_sub.add_parser(verb, help=helptext)
        sp.add_argument(
            "--port",
            required=True,
            help="Transport URI (e.g. serial:///dev/ttyUSB0 or loopback://).",
        )
        sp.add_argument(
            "--baud",
            type=int,
            default=None,
            help="Baud rate (serial only).",
        )
        sp.add_argument(
            "--timeout", type=float, default=2.0, help="Per-frame timeout in seconds."
        )
        if verb == "gift":
            sp.add_argument(
                "--kind",
                choices=["food", "toy"],
                default="food",
                help="What to send.",
            )
        sp.set_defaults(func=_make_ir_cmd(verb))

    # --- plugin ---------------------------------------------------------
    pp_ = sub.add_parser("plugin", help="Manage plugins.")
    pp_sub = pp_.add_subparsers(dest="plugin_cmd", required=True)

    pl = pp_sub.add_parser("list", help="List discovered plugins.")
    pl.set_defaults(func=cmd_plugin_list)

    pt = pp_sub.add_parser("trust", help="Add a plugin to the trust store.")
    pt.add_argument("path", help="Path to the plugin directory.")
    pt.set_defaults(func=cmd_plugin_trust)

    prv = pp_sub.add_parser("revoke", help="Remove a plugin from the trust store.")
    prv.add_argument("trust_key", help="<name>:<version>")
    prv.set_defaults(func=cmd_plugin_revoke)

    pck = pp_sub.add_parser("checksum", help="Compute SHA-256 of a plugin entry file.")
    pck.add_argument("path", help="Path to the .py file.")
    pck.set_defaults(func=cmd_plugin_checksum)

    prun = pp_sub.add_parser("run", help="Run a plugin's main action.")
    prun.add_argument("name", help="Plugin name.")
    prun.add_argument(
        "--port",
        default=None,
        help="Optional transport URI for IR-capable plugins.",
    )
    prun.set_defaults(func=cmd_plugin_run)

    # --- proximity ------------------------------------------------------
    pp_ = sub.add_parser(
        "proximity",
        help="Peer-pet sightings: log nearby OpenTamas, review the day's "
        "encounters, optionally summarise to Teams.",
    )
    pp_sub = pp_.add_subparsers(dest="proximity_cmd", required=True)

    ppr = pp_sub.add_parser(
        "record", help="Record a single peer sighting."
    )
    ppr.add_argument("peer_id", help="Opaque peer id (stable identifier).")
    ppr.add_argument("--nickname", default=None, help="Optional public nickname.")
    ppr.add_argument("--lang", default=None, help="Owner's language tag, e.g. 'ja'.")
    ppr.add_argument(
        "--rssi",
        default="unknown",
        help="Signal strength bucket: close / near / far / unknown.",
    )
    ppr.add_argument(
        "--at",
        type=float,
        default=None,
        help="Override the timestamp (unix seconds); defaults to now.",
    )
    ppr.set_defaults(func=cmd_proximity_record)

    ppl = pp_sub.add_parser("list", help="List recorded sightings.")
    ppl.add_argument(
        "--since",
        default=None,
        help="Only show sightings at or after this unix timestamp.",
    )
    ppl.set_defaults(func=cmd_proximity_list)

    ppd = pp_sub.add_parser(
        "digest",
        help="Summarise sightings into one entry per peer; optionally "
        "post the digest to Teams.",
    )
    ppd.add_argument(
        "--since",
        default=None,
        help="Only include sightings at or after this unix timestamp.",
    )
    ppd.add_argument(
        "--notify-teams",
        action="store_true",
        help="Also post the digest to Teams via the Power Automate webhook.",
    )
    ppd.add_argument(
        "--owner",
        default=None,
        help="Owner name to show in the Teams card (defaults to pet name).",
    )
    ppd.add_argument(
        "--webhook-url",
        default=None,
        help="Override the OPENTAMA_TEAMS_WEBHOOK env var.",
    )
    ppd.add_argument(
        "--timeout", type=float, default=10.0, help="HTTP timeout for Teams."
    )
    ppd.set_defaults(func=cmd_proximity_digest)

    ppc = pp_sub.add_parser("clear", help="Delete the proximity log.")
    ppc.set_defaults(func=cmd_proximity_clear)

    pps = pp_sub.add_parser(
        "scan",
        help="Listen on an IR transport for N seconds; log every peer seen.",
    )
    pps.add_argument(
        "--port",
        required=True,
        help="Transport URI (serial:///dev/ttyUSB0 or loopback://).",
    )
    pps.add_argument(
        "--baud",
        type=int,
        default=None,
        help="Baud rate (serial only).",
    )
    pps.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="How many seconds to listen (default: 30).",
    )
    pps.add_argument(
        "--rssi",
        default="unknown",
        help="Signal-strength bucket to tag sightings with "
        "(close / near / far / unknown). USB-IR has no RSSI; "
        "use whatever fits your physical setup.",
    )
    pps.set_defaults(func=cmd_proximity_scan)

    # --- teams ----------------------------------------------------------
    pt = sub.add_parser(
        "teams",
        help="Microsoft Teams integration (Power Automate webhook).",
    )
    pt_sub = pt.add_subparsers(dest="teams_cmd", required=True)
    ptn = pt_sub.add_parser(
        "notify", help="Post current pet status to Teams as an Adaptive Card."
    )
    ptn.add_argument(
        "--webhook-url",
        default=None,
        help="Override the OPENTAMA_TEAMS_WEBHOOK env var.",
    )
    ptn.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10).",
    )
    ptn.set_defaults(func=cmd_teams_notify)

    # --- display --------------------------------------------------------
    pd = sub.add_parser("display", help="Inspect available display backends.")
    pd_sub = pd.add_subparsers(dest="display_cmd", required=True)
    pdl = pd_sub.add_parser("list", help="List available displays.")
    pdl.set_defaults(func=cmd_display_list)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
