---
name: opentama
description: Use this skill when the user wants to interact with their OpenTama — a virtual Tamagotchi-style pet that grows only while connected to the company office WiFi, can talk to other OpenTamas over USB-attached IR adapters, can be extended via signed plugins, and can be rendered inside retro feature-phone (ガラケー) frames. Trigger phrases include "OpenTama", "たまごっち", "ガラケー", "check on my pet", "feed my tama", "出社", "office pet", "IR communication", "tama plugin", and any mention of an office-WiFi-based virtual pet. Use this skill to hatch a new pet, check its status (optionally inside a retro phone frame), feed/play/sleep, exchange greetings/gifts/visits with another OpenTama over IR, or install/run a sandboxed plugin. Do NOT use for unrelated WiFi diagnostics, general productivity tools, or other virtual-pet libraries.
license: MIT
---

# OpenTama — 出社促進キット

OpenTama is a tiny Tamagotchi that lives in the developer's terminal,
grows **only** while connected to the office WiFi, can chat with other
OpenTamas via USB-attached IR adapters, and can be extended with
sandboxed plugins. Optional: render the pet inside a retro
feature-phone (ガラケー) frame for the full atmosphere.

## Quick start

```bash
# Hatch a new pet (one-time setup).
python -m opentama init たまお OfficeWiFi-SSID

# Check on it — this also advances time-based growth/decay.
python -m opentama status

# Care actions.
python -m opentama feed
python -m opentama play
python -m opentama sleep

# Render inside a retro feature-phone frame.
python -m opentama status --display monokuro   # mono early-90s
python -m opentama status --display iro        # color flip phone
python -m opentama status --display wide       # late-era widescreen
python -m opentama display list

# Talk to another OpenTama over an IR USB adapter.
python -m opentama ir greet  --port serial:///dev/ttyUSB0
python -m opentama ir gift   --port serial:///dev/ttyUSB0 --kind food
python -m opentama ir visit  --port serial:///dev/ttyUSB0
python -m opentama ir listen --port serial:///dev/ttyUSB0  # responder side

# Plugins.
python -m opentama plugin list
python -m opentama plugin checksum path/to/entry.py
python -m opentama plugin trust    ~/.opentama/plugins/stats_card
python -m opentama plugin run      stats_card
python -m opentama plugin revoke   stats_card:0.1.0

# Start over.
python -m opentama reset
```

State is persisted at `~/.opentama/state.json` (override with
`OPENTAMA_STATE_PATH`). Plugins live in `~/.opentama/plugins/`
(override with `OPENTAMA_PLUGIN_DIR`). The trust store is at
`~/.opentama/trusted_plugins.json` (override with
`OPENTAMA_TRUST_STORE`).

## When to invoke this skill

Run `python -m opentama status` proactively whenever the user:
- Mentions OpenTama / たまごっち / their office pet.
- Says something like "I just got to the office" — `status` will pick
  up the WiFi change automatically.
- Asks how their pet is doing or what stage it's at.
- Asks to see the pet "on a ガラケー" / "on a flip phone" / "in a
  retro frame" → add `--display monokuro|iro|wide`.

Run the care actions (`feed`, `play`, `sleep`) when the user explicitly
asks to perform that action, or when `status` shows the matching stat
below ~30.

For IR features:
- "Greet/visit another tama over IR" → `ir greet` / `ir visit`.
- "Send a gift to my friend's tama" → `ir gift --kind food` (or `toy`).
- "Receive an IR ping" → `ir listen`.
- The transport URI is `serial:///dev/ttyUSB0` for typical USB-IR
  adapters; `loopback://` is for local testing.

For plugins:
- "Install/run a plugin" → walk through `plugin checksum` →
  edit `plugin.toml` → `plugin trust` → `plugin run`.
- The trust step is mandatory; loading an untrusted plugin will fail
  with a `NotTrustedError`.
- A file modified after being trusted will fail with an
  `IntegrityError` — that is by design.

If `status` reports "No OpenTama found", ask the user for a name and
their office SSID, then run `init`.

## Mechanics (for explaining things to the user)

### Core growth model

- Time-based ticks: every command updates state using the elapsed time
  since the previous tick. No background daemon needed.
- Growth points only accumulate while the current SSID matches the
  configured `company_ssid`.
- Stages by growth points: `egg → baby (10) → child (50) → teen (200)
  → adult (500) → elder (1500)`.
- Happiness decays 4× faster when away from the office than at it.
- Hunger and energy decay regardless of location; feed / sleep restore
  them.
- A stat at or below 15 marks the pet as "sick" and `status` will
  surface a `sick` event.

### IR communication

A small framed protocol over a USB-attached IR adapter:

```
+---------+---------+--------+------------------+---------+--------+
| "OT"    | version | type   | payload length   | payload | crc16  |
| 2 bytes | 1 byte  | 1 byte | 2 bytes (uint16) | N bytes | 2 bytes|
+---------+---------+--------+------------------+---------+--------+
```

CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF) over magic..payload.
Frame types: HELLO, STATE, GIFT, VISIT, ACK. Payloads are JSON for
legibility (small enough to fit comfortably in the 1 KB max payload).

High-level operations:
- `greet` — exchange names/stages, each side gets a small happiness bump.
- `gift {food|toy}` — sender's gift bumps the receiver's hunger (food)
  and happiness (food = small, toy = larger).
- `visit` — full handshake: greet → exchange → mutual happiness bonus.
  Records `met:<peer>` and `visited:<peer>` achievements on both sides.

### Plugin system (educational-grade security)

Plugins live in directories with:

```
my-plugin/
  plugin.toml    name, version, entrypoint, sha256, capabilities
  entry.py       defines a top-level `PLUGIN = MyPlugin()`
```

Capabilities (declared in the manifest, enforced at every API call):
`state.read`, `state.write`, `ir.transmit`, `ir.receive`, `display`.
Asking for a capability you didn't declare raises `CapabilityDenied`.

The trust model is "trust on first use": the user runs
`opentama plugin trust <dir>` once after checking the manifest, which
binds the plugin's `<name>:<version>` to its current SHA-256. Editing
the entry-point file invalidates the hash and refuses to load.

**What this protects against:** bit-rot, accidental edits, plugins
that try to do more than they declared.

**What it does NOT protect against:** a plugin you've explicitly
trusted that decides to `import os` and read your home directory.
True isolation would require OS-level sandboxing; this is an
educational tool, not a production runtime.

### Display backends (ガラケー)

Three retro feature-phone frames render the pet from a `StateView`
snapshot:

- `monokuro` — early-90s monochrome candybar, narrow LCD, dialpad.
- `iro` — mid-2000s color flip phone, status bar with signal/battery.
- `wide` — late-era widescreen ガラケー, mood indicator, app strip.

All use ASCII-only borders for terminal portability and a
visual-width-aware padder that handles Japanese names and emoji
correctly.

## Files

- `opentama/wifi.py` — cross-platform SSID detection (macOS, Linux,
  Windows).
- `opentama/state.py` — JSON-backed `TamaState` dataclass.
- `opentama/stages.py` — life stages and ASCII art.
- `opentama/core.py` — the `Tamagotchi` class (DI: `ssid_provider`,
  `clock`).
- `opentama/cli.py` — argparse CLI behind `python -m opentama`.
- `opentama/ir/` — protocol, transport (`SerialIRTransport`,
  `LoopbackIRTransport`), and `Session` (greet/gift/visit).
- `opentama/plugins/` — capability-based plugin API, loader, and trust
  store.
- `opentama/displays/` — three retro feature-phone display backends
  plus a visual-width-aware layout helper.
- `examples/plugins/stats_card/` — a sample display plugin.
- `examples/plugins/ir_ping/` — a sample IR plugin (transmit + receive).

## Testing

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers WiFi detection (mocked subprocess), state
persistence, growth/decay over time, the CLI, the IR wire protocol
(including CRC edge cases and resyncing on garbage), IR transports,
high-level IR sessions over a paired loopback, plugin manifest
parsing, SHA-256 integrity, trust-store semantics, capability gate
enforcement, and rendered output for each display.
