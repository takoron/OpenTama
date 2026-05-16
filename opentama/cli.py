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
